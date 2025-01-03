#!/usr/bin/env python
"""
Update the expected test outputs and inputs for rsmsummarize and rsmcompare tests.

This script assumes that you have already run `nose2 -s tests` and ran the entire
test suite. By doing so, the output has been generated under the given outputs
directory. And that is what will be used to generate the new expected output
under `tests/data/experiments`.

#############################################################################################
# IMPORTANT: DO NOT RUN THIS SCRIPT BEFORE RUNNING THE TEST SUITE OR IT WILL BE DISASTROUS. #
#############################################################################################

The script works as follows. For each experiment test:
- The script locates the output under the updated outputs directory.
- New and changed files in this directory are copied over to the expected test
  output location.
- Old files in the expected test output are deleted.
- Files that are already in the expected test output and have not changed are
  left alone.
- Directories that are missing or empty under the updated test outputs are shown.
- For rsmsummarize and rsmcompare tests, the same logic is also applied to input
  data. It is assumed that the input experiments are copies of the experiments
  from existing tests.

Note: If running this script results in changes to the inputs for rsmcompare
or rsmsummarize tests, you will need to first re-run the tests for those two
tools and then, potentially, run this script again to update their test outputs.

See `documentation <https://rsmtool.readthedocs.io/en/main/contributing.html#writing-new-functional-tests>`_
for a further explanation of this process.

The script prints a log detailing the changes made for each experiment test.

:author: Nitin Madnani
:author: Anastassia Loukina
:author: Jeremy Biggs

:organization: ETS
"""

import argparse
import re
import sys
from pathlib import Path

from rsmtool.test_utils import FileUpdater


def main():  # noqa: D103
    # set up an argument parser
    parser = argparse.ArgumentParser(prog="update_test_files.py")
    parser.add_argument(
        "--tests",
        dest="tests_dir",
        required=True,
        help="The path to the existing RSMTool tests directory",
    )
    parser.add_argument(
        "--outputs",
        dest="outputs_dir",
        required=True,
        help="The path to the directory containing the updated test "
        "outputs (usually `test_outputs`)",
    )

    # parse given command line arguments
    args = parser.parse_args()

    # print out a reminder that the user should have run the test suite
    run_test_suite = input("Have you already run the whole test suite? (y/n): ")
    if run_test_suite == "n":
        print("Please run the whole test suite using `nose2 -s tests` before running this script.")
        sys.exit(0)
    elif run_test_suite != "y":
        print("Invalid answer. Exiting.")
        sys.exit(1)
    else:
        print()

    # iterate over the given tests directory and find all files named
    # `test_experiment_*.py` and get their suffixes for use with the
    # FileUpdater object.
    suffixes = [
        re.sub(r"test_experiment_", "", p.stem) for p in Path("tests").glob("test_experiment_*.py")
    ]

    # instantiate a FileUpdater object
    updater = FileUpdater(
        test_suffixes=suffixes,
        tests_directory=args.tests_dir,
        updated_outputs_directory=args.outputs_dir,
    )

    # run the file updates
    updater.run()

    # now print the report from the updated object
    updater.print_report()


if __name__ == "__main__":
    main()
