from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def flist(
    system: str,
    flags: list | None = [],
    output: str | None = None,
    verbose: bool = False,
) -> str:
    """Wrapper around the Edalize flist tool.

    This method calls Fusesoc with the 'flist' target that is assumed to use the
    Edalize flist tool.

    Args:
        system:  a Fusesoc VLNV.
        flags:   a list of flags to pass to Fusesoc.
        output:  an optional filelist file name to write to.
        verbose: run FuseSoC in verbose mode

    The output filename can be an absolute path defined from the directory root using
    "/", a relative filepath to wherever the script was called using "./", or a plain
    filename that gets output parallel to the core file.

    If no output filename is specified then the filelist name defaults to either
    "filelist.f" or "<core_file>.f" depending on which version of Fusesoc is installed.

    """
    try:
        core_info = subprocess.check_output(
            ["fusesoc", "core", "show", system],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.output)

    for line in core_info.split("\n"):
        if line.startswith("Core root:"):
            _, path = line.split(":")
            core_root = path.strip()
        if line.startswith("Core file:"):
            _, filename = line.split(":")
            core_file = filename.strip()

    if output:
        output_expanded = os.path.expandvars(output)
        if output_expanded.startswith("/") or output_expanded.startswith("./"):
            dst = output_expanded
        else:
            dst = os.path.join(core_root, output_expanded)
    else:
        try:
            dst = os.path.join(core_root, core_file.replace(".core", ".f"))
        except NameError:
            dst = os.path.join(core_root, "filelist.f")

    with tempfile.TemporaryDirectory() as dir:
        cmd = ["fusesoc"]
        if verbose:
            cmd.append("--verbose")
        cmd.extend(
            [
                "run",
                "--no-export",
                "--build-root",
                os.path.realpath(dir),
                "--target",
                "flist",
            ],
        )

        if flags:
            for flag in flags:
                cmd.extend(["--flag", flag])

        cmd.append(system)

        if verbose:
            print(" ".join(cmd))

        try:
            cmd_output = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise SystemExit(e.output)

        if verbose:
            print(cmd_output)

        src = glob.glob(f"{dir}/**/*.f", recursive=True)[0]

        soc_repo_root = os.environ.get("SOC_REPO_ROOT", "unused")
        with open(dst, "w") as ofile:
            with open(src) as ifile:
                for line in ifile.readlines():
                    line.rstrip()
                    line = line.replace(soc_repo_root, "${SOC_REPO_ROOT}")
                    ofile.write(line)

        return dst


def get_parser():
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
            prog,
            max_help_position=80,
            width=220,
        ),
    )
    parser.add_argument(
        "system",
        help="Fusesoc VLNV",
    )
    parser.add_argument(
        "-f",
        "--flag",
        action="append",
        help="Fusesoc flags",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="override the filelist file name and path",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="run Fusesoc in verbose mode",
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    from fusesoc.fusesoc import Fusesoc

    Fusesoc.init_logging(verbose=args.verbose, monochrome=False)

    dst = flist(args.system, args.flag, args.output, args.verbose)
    logger.info(f"Created filelist at {dst}")
