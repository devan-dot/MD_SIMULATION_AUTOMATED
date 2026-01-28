DEPENDENCIES
> Python 3.8 or newer
> GROMACS 2020 or newer (GPU-enabled build recommended)
> Linux environment (tested on Ubuntu)


Stages->Energy Minimization → Multi-step Equilibration → Production MD

REQUIRED FILES (FROM CHARMM-GUI):
Structure & Topology
> step3_input.gro
> step3_input.pdb
> step3_input.psf
> topol.top
> index.ndx
> MD parameter files

The script can automatically create multiple equilibration steps (maximum 5) with progressive position restraint reduction.

Default restraint schedule:

Step 1 → FC_BB 400 | FC_SC 40
Step 2 → FC_BB 300 | FC_SC 30
Step 3 → FC_BB 200 | FC_SC 20
Step 4 → FC_BB 100 | FC_SC 10
Step 5 → FC_BB 50  | FC_SC 5

Final out:
> production.tpr
> production.gro
> production.log
> production.edr
