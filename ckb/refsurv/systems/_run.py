# SPDX-License-Identifier: MIT OR Apache-2.0
"""Runs the reference-survival cases against one system, through the same
isolating driver the kernel benchmarks use."""
from .. import cases, report
from ... import driver


def main(system, module):
    class Shim:
        FUZZY = None
        case_list = staticmethod(cases.case_list)
        summarise = staticmethod(report.summarise)

        @staticmethod
        def run_boolean_case(c):
            return cases.run_case(c, system)
    driver.main(Shim, module, default_kinds=",".join(cases.CLASSES))
