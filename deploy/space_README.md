---
title: Fed Sentiment Analyzer
emoji: 🦅
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Fed Sentiment Analyzer

Paste FOMC minutes, a statement, or a speech excerpt and get a live
hawkish/dovish/neutral classification from a FOMC-specific transformer
(`tim9510019/FOMC-RoBERTa`) combined with a transparent phrase-lexicon
baseline.

Source and full docs: https://github.com/MaciSekander/fed-sentiment-analyzer

This Space is auto-deployed from that repo's `main` branch on every push
(see `.github/workflows/deploy-space.yml`) -- it is not developed here
directly.

Note: the first request after a restart can take 10-30 seconds while the
model loads on this Space's CPU tier.
