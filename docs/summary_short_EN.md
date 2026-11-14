# ECO: how many real sources are behind what reaches you?

AI makes it almost free to clone a news story across dozens of sites, fake a photo's date and clone a voice for a WhatsApp voice note. People and AI agents count that repetition as confirmation.

ECO answers three questions with a plain-language verdict. How many real sources are there? An LLM extracts the facts in each article and an auditable rule, in chronological order, separates original reporting from repetition. Where does this photo or video come from, and was it made by AI? It verifies C2PA credentials, AI markers in metadata and forensic filters. Is this voice real? An AASIST-L detector retrained on WhatsApp-like audio. A voice note or screenshot becomes a claim that an agent investigates live, ending with the source to read first and why. It runs as a bilingual web app, a Chrome extension and an MCP server.

Results: on 18 held-out worlds ECO counts sources correctly 92 % of the time versus 83 % for text similarity; with its report, an agent says "confirmed" with a single origin 22 % of the time instead of 51 %; with C2PA, rewritten copies that reuse the signed photo go from 0 % to 100 % detection. The off-the-shelf voice detector performs like chance on real audio (48.5 % error); retrained, it drops to 28.7 % and barely degrades under compression. ECO does not say what is true: it shows the evidence.
