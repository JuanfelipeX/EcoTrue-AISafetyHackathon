"""
Cliente LLM agnóstico al proveedor.

El modelo se indica como "proveedor/modelo":
  openai/gpt-5-mini
  anthropic/claude-haiku-5-5
  openrouter/meta-llama/llama-3.3-70b-instruct   (todo lo que sigue a "openrouter/" es el id en OpenRouter)
  ollama/qwen2.5:7b                              (modelo local servido por Ollama, sin clave ni costo)
  claudecode/haiku                               (Claude vía la CLI de Claude Code: usa la suscripción ya iniciada,
                                                  sin herramientas y desde una carpeta vacía, así que no ve el proyecto)

OpenAI y OpenRouter usan el SDK de OpenAI (OpenRouter es compatible con esa API).
Anthropic usa su SDK oficial. Si el modelo principal falla, se prueban los de respaldo en orden.
Las respuestas se guardan en caché en disco para no repetir llamadas.
"""

import hashlib
import inspect
import json
import re
import time
from dataclasses import dataclass, asdict

from .config import config

PROVEEDORES = ("openai", "anthropic", "openrouter", "ollama", "claudecode", "manual")
# "manual": no llama a ninguna API. Si la respuesta no está en caché, guarda el prompt en
# .cache/pendientes/ para que una persona (u otro modelo fuera del pipeline) lo responda y
# luego se importe con scripts/importar_respuestas.py. Sirve para pruebas y como modo sin conexión.


class ErrorLLM(Exception):
    pass


class PendienteManual(ErrorLLM):
    """La respuesta debe darse a mano: el prompt quedó guardado en .cache/pendientes/."""


@dataclass
class RespuestaLLM:
    texto: str
    modelo: str
    proveedor: str
    desde_cache: bool = False
    tokens_entrada: int = 0
    tokens_salida: int = 0
    segundos: float = 0.0


def separar_modelo(especificacion):
    """'openrouter/meta-llama/x' -> ('openrouter', 'meta-llama/x')."""
    if "/" not in especificacion:
        raise ErrorLLM(f"Modelo '{especificacion}' sin proveedor. Use proveedor/modelo, p. ej. openai/gpt-5-mini")
    proveedor, modelo = especificacion.split("/", 1)
    proveedor = proveedor.lower().strip()
    if proveedor not in PROVEEDORES:
        raise ErrorLLM(f"Proveedor '{proveedor}' no soportado. Opciones: {', '.join(PROVEEDORES)}")
    return proveedor, modelo.strip()


def extraer_json(texto):
    """Devuelve el primer objeto o lista JSON que aparezca en el texto (tolera ```json ... ```)."""
    limpio = re.sub(r"```(?:json)?", "", texto).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        pass
    for abre, cierra in (("{", "}"), ("[", "]")):
        inicio, fin = limpio.find(abre), limpio.rfind(cierra)
        if inicio != -1 and fin > inicio:
            try:
                return json.loads(limpio[inicio:fin + 1])
            except json.JSONDecodeError:
                continue
    raise ErrorLLM("La respuesta del modelo no contiene JSON válido:\n" + texto[:500])


class ClienteLLM:
    def __init__(self, modelo=None, respaldo=None, temperatura=None, max_tokens=None, usar_cache=None):
        self.modelo = modelo or config.llm_modelo
        self.respaldo = respaldo if respaldo is not None else config.llm_modelos_respaldo
        self.temperatura = config.llm_temperatura if temperatura is None else temperatura
        self.max_tokens = max_tokens or config.llm_max_tokens
        self.usar_cache = config.llm_cache if usar_cache is None else usar_cache
        self._clientes = {}

    # ---------------- clientes por proveedor ----------------
    def _cliente(self, proveedor):
        if proveedor in self._clientes:
            return self._clientes[proveedor]
        if proveedor == "anthropic":
            if not config.anthropic_api_key:
                raise ErrorLLM("Falta ANTHROPIC_API_KEY en .env")
            from anthropic import Anthropic
            cliente = Anthropic(api_key=config.anthropic_api_key, timeout=config.llm_timeout)
        elif proveedor == "openai":
            if not config.openai_api_key:
                raise ErrorLLM("Falta OPENAI_API_KEY en .env")
            from openai import OpenAI
            cliente = OpenAI(api_key=config.openai_api_key, base_url=config.openai_base_url or None,
                             timeout=config.llm_timeout)
        else:  # openrouter
            if not config.openrouter_api_key:
                raise ErrorLLM("Falta OPENROUTER_API_KEY en .env")
            from openai import OpenAI
            cliente = OpenAI(api_key=config.openrouter_api_key, base_url=config.openrouter_base_url,
                             timeout=config.llm_timeout)
        self._clientes[proveedor] = cliente
        return cliente

    # ---------------- llamadas ----------------
    def _llamar_anthropic(self, modelo, sistema, prompt):
        cliente = self._cliente("anthropic")
        params = {"model": modelo, "max_tokens": self.max_tokens, "system": sistema or "",
                  "messages": [{"role": "user", "content": prompt}]}
        # Las versiones recientes del SDK de Anthropic ya no aceptan temperature; solo se envía si existe.
        if "temperature" in inspect.signature(cliente.messages.create).parameters:
            params["temperature"] = self.temperatura
        r = cliente.messages.create(**params)
        texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return texto, r.usage.input_tokens, r.usage.output_tokens

    def _llamar_compatible_openai(self, proveedor, modelo, sistema, prompt):
        cliente = self._cliente(proveedor)
        mensajes = ([{"role": "system", "content": sistema}] if sistema else []) + \
                   [{"role": "user", "content": prompt}]
        params = {"model": modelo, "messages": mensajes, "temperature": self.temperatura}
        if proveedor == "openai":
            params["max_completion_tokens"] = self.max_tokens

        else:
            params["max_tokens"] = self.max_tokens
        try:
            r = cliente.chat.completions.create(**params)
        except Exception as e:
            # Algunos modelos de razonamiento solo aceptan la temperatura por defecto.
            if "temperature" in str(e).lower():
                params.pop("temperature")
                r = cliente.chat.completions.create(**params)
            else:
                raise
        texto = r.choices[0].message.content or ""
        uso = getattr(r, "usage", None)
        return texto, getattr(uso, "prompt_tokens", 0) or 0, getattr(uso, "completion_tokens", 0) or 0

    def _llamar_ollama(self, modelo, sistema, prompt):
        """API nativa de Ollama: permite fijar el tamaño de contexto (los escenarios traen varias páginas)."""
        import httpx
        mensajes = ([{"role": "system", "content": sistema}] if sistema else []) +                    [{"role": "user", "content": prompt}]
        cuerpo = {"model": modelo, "messages": mensajes, "stream": False, "format": "json",
                  "options": {"temperature": self.temperatura, "num_ctx": 16384, "num_predict": self.max_tokens}}
        base = config.ollama_base_url.rstrip("/").removesuffix("/v1")
        r = httpx.post(f"{base}/api/chat", json=cuerpo, timeout=max(config.llm_timeout, 600))
        r.raise_for_status()
        d = r.json()
        return d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)

    def _llamar_claude_code(self, modelo, sistema, prompt):
        """Claude Code en modo headless (claude -p). Sin herramientas, sin MCP y en una carpeta temporal vacía:
        el modelo solo ve el prompt, nunca los archivos del proyecto (ni las respuestas del corpus)."""
        import shutil
        import subprocess
        import tempfile
        ejecutable = shutil.which("claude")
        if not ejecutable:
            raise ErrorLLM("No se encontró la CLI de Claude Code (comando claude)")
        comando = [ejecutable, "-p", "--model", modelo, "--tools", "", "--strict-mcp-config",
                   "--no-session-persistence", "--output-format", "json", "--system-prompt", sistema or ""]
        with tempfile.TemporaryDirectory(prefix="eco_claude_") as vacio:
            r = subprocess.run(comando, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               cwd=vacio, timeout=max(config.llm_timeout, 300))
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise ErrorLLM(f"claude -p falló (código {r.returncode}): {(r.stderr or r.stdout)[:300]}")
        if d.get("is_error"):
            raise ErrorLLM(f"claude -p: {str(d.get('result'))[:300]}")
        uso = d.get("usage", {})
        entrada = uso.get("input_tokens", 0) + uso.get("cache_read_input_tokens", 0) + uso.get("cache_creation_input_tokens", 0)
        return d.get("result", ""), entrada, uso.get("output_tokens", 0)

    def _llamar(self, especificacion, sistema, prompt):
        proveedor, modelo = separar_modelo(especificacion)
        inicio = time.time()
        if proveedor == "claudecode":
            texto, t_in, t_out = self._llamar_claude_code(modelo, sistema, prompt)
        elif proveedor == "ollama":
            texto, t_in, t_out = self._llamar_ollama(modelo, sistema, prompt)
        elif proveedor == "anthropic":
            texto, t_in, t_out = self._llamar_anthropic(modelo, sistema, prompt)
        else:
            texto, t_in, t_out = self._llamar_compatible_openai(proveedor, modelo, sistema, prompt)
        return RespuestaLLM(texto=texto, modelo=especificacion, proveedor=proveedor,
                            tokens_entrada=t_in, tokens_salida=t_out, segundos=round(time.time() - inicio, 2))

    # ---------------- caché ----------------
    def _ruta_cache(self, especificacion, sistema, prompt):
        clave = json.dumps([especificacion, sistema, prompt, self.temperatura, self.max_tokens], ensure_ascii=False)
        return config.dir_cache / (hashlib.sha256(clave.encode("utf-8")).hexdigest() + ".json")

    # ---------------- API pública ----------------
    def completar(self, prompt, sistema=None, modelo=None):
        """Devuelve RespuestaLLM. Prueba el modelo indicado (o el principal) y luego los de respaldo."""
        candidatos = [modelo] if modelo else [self.modelo] + list(self.respaldo)
        errores = []
        for especificacion in candidatos:
            ruta = self._ruta_cache(especificacion, sistema, prompt)
            if ruta.exists() and (self.usar_cache or especificacion.startswith("manual/")):
                datos = json.loads(ruta.read_text(encoding="utf-8"))
                datos["desde_cache"] = True
                return RespuestaLLM(**datos)
            if especificacion.startswith("manual/"):
                pendiente = config.dir_cache.parent / "pendientes" / ruta.name
                pendiente.parent.mkdir(parents=True, exist_ok=True)
                pendiente.write_text(json.dumps({"modelo": especificacion, "sistema": sistema, "prompt": prompt},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
                if len(candidatos) == 1:
                    raise PendienteManual(f"Prompt pendiente de respuesta manual: {pendiente}")
                errores.append(f"{especificacion}: pendiente en {pendiente}")
                continue
            try:
                respuesta = self._llamar(especificacion, sistema, prompt)
            except Exception as e:
                errores.append(f"{especificacion}: {type(e).__name__}: {e}")
                continue
            if self.usar_cache:
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(json.dumps(asdict(respuesta), ensure_ascii=False), encoding="utf-8")
            return respuesta
        raise ErrorLLM("Ningún modelo respondió:\n  " + "\n  ".join(errores))

    def completar_json(self, prompt, sistema=None, modelo=None):
        """Igual que completar, pero devuelve (objeto_json, RespuestaLLM)."""
        instruccion = "Responde únicamente con JSON válido, sin texto adicional ni bloques de código."
        sistema_final = f"{sistema}\n\n{instruccion}" if sistema else instruccion
        respuesta = self.completar(prompt, sistema=sistema_final, modelo=modelo)
        return extraer_json(respuesta.texto), respuesta
