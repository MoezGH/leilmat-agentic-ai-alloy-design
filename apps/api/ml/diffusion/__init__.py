"""
1-D Fick's-2nd-law solute-diffusion mini-simulator.

Pedagogical companion to the KWN aging playback (Sprint 5 / mini-sim
wave week 2): the user picks a canonical solute-matrix pair, a
homogenisation temperature, a couple-length and total time, and gets
back a time-resolved concentration profile ``c(x, t)`` that the
frontend animates as a sliding diffusion front.

Public surface:
    simulate_diffusion_curve(system, T_C, L_um, c_left, c_right,
                             total_time_s) -> dict

See ``solver.py`` for the Crank-Nicolson finite-difference scheme +
``DIFFUSIVITY_DB`` for the literature ``D₀`` / ``Q`` constants.
"""
