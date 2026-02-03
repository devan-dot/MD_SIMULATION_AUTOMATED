#!/usr/bin/env python3

import os
import shutil
import subprocess

MAX_EQ_STEPS = 5
POSRES_SCHEDULE = [(400, 40), (300, 30), (200, 20), (100, 10), (50, 5)]


BANNER = r"""
  ____                                      ____                
 / ___|_ __ ___  _ __ ___   __ _           |  _ \ _   _ _ __  
| |  _| '__/ _ \| '_ ` _ \ / _` |  _____   | |_) | | | | '_ \ 
| |_| | | | (_) | | | | | | (_| | |_____|  |  _ <| |_| | | | |
 \____|_|  \___/|_| |_| |_|\__,_|          |_| \_\\__,_|_| |_|
                                                         
          >> Automated GROMACS CHARMM-GUI Pipeline <<
"""

# ---------------- MDP PARSER ---------------- #

def read_mdp(filepath):
    params = {}
    lines = []

    with open(filepath, "r") as f:
        for line in f:
            stripped = line.strip()

            if "=" in line and not stripped.startswith(";"):
                key = line.split("=")[0].strip()
                params[key] = line
            lines.append(line)

    return params, lines


def write_mdp(filepath, lines):
    with open(filepath, "w") as f:
        f.writelines(lines)


def edit_mdp(filepath):
    params, lines = read_mdp(filepath)

    print(f"\nEditing {filepath}")
    print("Available parameters (current values shown):")

    for k, line in params.items():
        current_val = line.split("=", 1)[1].strip()
        print(f" - {k:<25} = {current_val}")

    while True:
        key = input("\nParameter to edit (or 'no'): ").strip()
        if key.lower() == "no":
            break

        if key not in params:
            print("Parameter not found.")
            continue

        new_val = input("New value: ").strip()
        new_line = f"{key:<25} = {new_val}\n"

        for i, line in enumerate(lines):
            if line.strip().startswith(key):
                lines[i] = new_line
                break

    write_mdp(filepath, lines)
    print(f"{filepath} updated.")


# ---------------- GMX RUNNER ---------------- #

def run_cmd(cmd):
    print("\nRunning:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Command failed. Exiting.")
        exit(1)


# ---------------- MINIMIZATION ---------------- #

def run_minimization(mdp):
    run_cmd([
        "gmx", "grompp",
        "-f", mdp,
        "-o", "minimization.tpr",
        "-c", "step3_input.gro",
        "-r", "step3_input.gro",
        "-p", "topol.top",
        "-n", "index.ndx",
        "-maxwarn", "1"
    ])

    run_cmd(["gmx", "mdrun", "-v", "-deffnm", "minimization"])


# ---------------- EQUILIBRATION ---------------- #

def prepare_equilibration_files(base_mdp, steps):
    base_params, base_lines = read_mdp(base_mdp)

    for i in range(steps):
        bb, sc = POSRES_SCHEDULE[i]
        new_lines = []

        for line in base_lines:
            if line.strip().startswith("define"):
                new_lines.append(
                    f"define                  = -DPOSRES -DPOSRES_FC_BB={bb} -DPOSRES_FC_SC={sc}\n"
                )
            else:
                new_lines.append(line)

        out_name = f"step4.1.{i+1}_equilibration.mdp"
        write_mdp(out_name, new_lines)
        print(f"Created {out_name}")


def run_equilibration(steps):
    prev_gro = "minimization.gro"

    for i in range(1, steps + 1):
        mdp = f"step4.1.{i}_equilibration.mdp"
        tpr = f"equilibration{i}.tpr"
        prefix = f"equilibration{i}"

        run_cmd([
            "gmx", "grompp",
            "-f", mdp,
            "-o", tpr,
            "-c", prev_gro,
            "-r", "step3_input.gro",
            "-p", "topol.top",
            "-n", "index.ndx",
            "-maxwarn", "1"
        ])

        run_cmd([
            "gmx", "mdrun",
            "-v",
            "-deffnm", prefix,
            "-nb", "gpu"
        ])

        prev_gro = f"{prefix}.gro"

    return prev_gro


# ---------------- PRODUCTION ---------------- #

def run_production(mdp, input_gro):
    run_cmd([
        "gmx", "grompp",
        "-f", mdp,
        "-o", "production.tpr",
        "-c", input_gro,
        "-p", "topol.top",
        "-n", "index.ndx",
        "-maxwarn", "1"
    ])

    run_cmd([
        "gmx", "mdrun",
        "-v",
        "-deffnm", "production",
        "-nb", "gpu",
        "-pme", "gpu"
    ])


# ---------------- MAIN WORKFLOW ---------------- #

def main():
    # Print the ASCII banner
    print(BANNER)

    min_mdp = input("Minimization MDP filename: ").strip()
    eq_mdp = input("Equilibration MDP filename: ").strip()
    prod_mdp = input("Production MDP filename: ").strip()

    if input("Edit minimization MDP? (y/n): ").lower() == "y":
        edit_mdp(min_mdp)

    multi_eq = input("Multiple equilibration runs? (y/n): ").lower()

    if multi_eq == "y":
        steps = int(input(f"How many? (max {MAX_EQ_STEPS}): "))
        steps = min(steps, MAX_EQ_STEPS)
        prepare_equilibration_files(eq_mdp, steps)

        print("\nYou will now edit equilibration parameters.")
        print("Step 1 will be edited first.")

        edit_mdp("step4.1.1_equilibration.mdp")

        same_for_all = input("Use same parameters for remaining equilibration steps? (y/n): ").lower()

        if same_for_all == "y":
            base_params, base_lines = read_mdp("step4.1.1_equilibration.mdp")

            for i in range(2, steps + 1):
                bb, sc = POSRES_SCHEDULE[i-1]
                new_lines = []

                for line in base_lines:
                    if line.strip().startswith("define"):
                        new_lines.append(
                            f"define                  = -DPOSRES -DPOSRES_FC_BB={bb} -DPOSRES_FC_SC={sc}\n"
                        )
                    else:
                        new_lines.append(line)

                write_mdp(f"step4.1.{i}_equilibration.mdp", new_lines)
                print(f"Updated step4.1.{i}_equilibration.mdp with same settings.")
        else:
            prev_template = "step4.1.1_equilibration.mdp"

            for i in range(2, steps + 1):
                bb, sc = POSRES_SCHEDULE[i-1]

                print(f"\nEditing equilibration step {i}")
                edit_mdp(prev_template)

                params, lines = read_mdp(prev_template)
                new_lines = []

                for line in lines:
                    if line.strip().startswith("define"):
                        new_lines.append(
                            f"define                  = -DPOSRES -DPOSRES_FC_BB={bb} -DPOSRES_FC_SC={sc}\n"
                        )
                    else:
                        new_lines.append(line)

                current_file = f"step4.1.{i}_equilibration.mdp"
                write_mdp(current_file, new_lines)

                same_as_this = input(f"Use these settings for remaining steps after {i}? (y/n): ").lower()
                if same_as_this == "y":
                    for j in range(i + 1, steps + 1):
                        bb2, sc2 = POSRES_SCHEDULE[j-1]
                        copied_lines = []

                        for line in new_lines:
                            if line.strip().startswith("define"):
                                copied_lines.append(
                                    f"define                  = -DPOSRES -DPOSRES_FC_BB={bb2} -DPOSRES_FC_SC={sc2}\n"
                                )
                            else:
                                copied_lines.append(line)

                        write_mdp(f"step4.1.{j}_equilibration.mdp", copied_lines)
                        print(f"Updated step4.1.{j}_equilibration.mdp")

                    break

                prev_template = current_file

    else:
        steps = 1
        shutil.copy(eq_mdp, "step4.1.1_equilibration.mdp")
        if input("Edit equilibration MDP? (y/n): ").lower() == "y":
            edit_mdp("step4.1.1_equilibration.mdp")

    if input("Edit production MDP? (y/n): ").lower() == "y":
        edit_mdp(prod_mdp)

    print("\n--- STARTING SIMULATION PIPELINE ---")

    run_minimization(min_mdp)
    final_gro = run_equilibration(steps)
    run_production(prod_mdp, final_gro)

    print("\nALL SIMULATIONS COMPLETED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
