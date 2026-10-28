# Fly Séance

**A séance with a simulated fruit-fly brain.** You ask a question. A local Gemma
model, the medium, turns it into an offering — nectar, a bitter herb, a touch on the
antenna. The wiring diagram of a real fly brain (the FlyWire connectome, ~139,000
neurons) is simulated, and the fly's body answers: it reaches for the nectar, it
grooms the touch away, or it stays still. The medium then speaks for it.

Everything runs on your own machine. No cloud model, no API key.

> The fly does not understand your question. What is real is how its simulated
> body responds to the offering, computed from the wiring of an actual fly.
> See [docs/SCIENCE.md](docs/SCIENCE.md).

## How it works

1. **Consecrate** — Gemma reads the question and returns an offering as strict JSON
   (a rate in Hz for each sensory group), validated and clamped in code.
2. **Channel** — a leaky integrate-and-fire model of the whole fly brain
   (Shiu et al., *Nature* 2024) is driven by that offering for one simulated second,
   over several trials.
3. **Read** — code, not the model, reads the motor response: MN9 fires → the fly
   feeds (*yes*); aBN1 and the antennal descending neurons fire → it grooms (*it
   brushes the question off*); neither → stillness (*no*).
4. **Speak** — Gemma voices the answer, given only the verdict and the numbers.

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it

```bash
uv venv && uv pip install -e ".[dev]"
python scripts/fetch_connectome.py     # ~90 MB, checksummed, into data/
ollama pull gemma4                     # the medium
```

## Status

- [x] Connectome model with competing offerings (`brain.py`), one process per trial (`worker.py`)
- [ ] Oracle: offering validation, parallel trials, verdict (`oracle.py`)
- [ ] Medium: Gemma via Ollama (`medium.py`)
- [ ] Séance page with a live spike raster (`server.py`, `web/`)

## Credits

Built on the model of Shiu et al. (2024, MIT) and the FlyWire connectome
(Dorkenwald et al. 2024; Schlegel et al. 2024). See [NOTICE.md](NOTICE.md).

## License

MIT — see [LICENSE](LICENSE).
