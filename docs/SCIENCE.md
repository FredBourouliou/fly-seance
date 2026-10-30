# What is real here, and what isn't

## Real
- **The wiring.** The FlyWire connectome: the complete synaptic wiring diagram of
  one adult female *Drosophila melanogaster* brain, reconstructed from electron
  microscopy (Dorkenwald et al., *Nature* 2024; Schlegel et al., *Nature* 2024).
- **The model.** A leaky integrate-and-fire network built on that wiring, with
  excitatory/inhibitory signs from predicted neurotransmitters (Shiu et al.,
  *Nature* 2024). Parameters are the paper's: resting −52 mV, threshold −45 mV,
  membrane time constant 20 ms, synaptic time constant 5 ms, refractory 2.2 ms,
  synaptic delay 1.8 ms, weight 0.275 mV per synapse.
- **The behaviours.** The paper shows this model predicts which neurons drive the
  proboscis extension in response to sugar (MN9), that bitter input suppresses it,
  and which pathways drive antennal grooming from Johnston's organ neurons.

## Not real
- **The fly does not hear, understand or answer the question.** It receives an
  offering chosen by the medium (Gemma) and its simulated body responds to that
  offering. The "answer" is our reading of a motor response.
- **It is not a living or conscious fly.** It is a simplified point-neuron model:
  no dendrites, no neuromodulation, no learning, no body or sensory feedback.
- **It is one brain.** Wiring varies between individuals.

## What the séance adds
The medium's choice of offering largely sets the outcome. What the connectome adds
is the arbitration when offerings compete (nectar *and* bitter *and* a touch). Over 22
recorded séances, the rule "the strongest offering wins" predicted 21 verdicts; the
22nd was a three-way mix that only the wiring could settle.

The Poisson input varies from trial to trial, but the five trials of a séance use
fixed seeds (1 to 5), on purpose: the same offering always gives the same numbers, so
any verdict can be audited. Those 22 séances were all unanimous, so at the rates
Gemma chooses the trials add little beyond the ritual. Disagreement remains possible
near a threshold, and the page shows it when it happens.

## Measured on the dev machine (FlyWire 630, 1 s simulated, single trials)

| Offering | Neurons active | MN9 | aBN1 |
|----------|----------------|-----|------|
| sugar 21 GRNs @150 Hz | 375–399 | 78–97 Hz | 0 |
| bitter 21 GRNs @150 Hz | 76–79 | 0 | 0 |
| antenna JON-CE 70 @150 Hz | 303 | 0 | 52 Hz |

## References
- Dorkenwald, S. et al. Neuronal wiring diagram of an adult brain. *Nature* 634 (2024).
- Schlegel, P. et al. Whole-brain annotation and multi-connectome cell typing quantifies circuit stereotypy in *Drosophila*. *Nature* 634 (2024).
- Shiu, P.K. et al. A *Drosophila* computational brain model reveals sensorimotor processing. *Nature* 634 (2024).
  Code: https://github.com/philshiu/Drosophila_brain_model (MIT).
