# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import unicode_literals

import random

from projectq import MainEngine
from projectq.cengines import (LimitedCapabilityEngine,
                               AutoReplacer,
                               DecompositionRuleSet,
                               DummyEngine)
from projectq.setups.decompositions import swap2cnot
from . import (addition_decompositions,
               increment_decompositions,
               multi_not_decompositions)
from .increment_decompositions import (
    do_increment_with_no_controls_and_n_dirty
)
from ._test_util import fuzz_permutation_circuit
from .gates import Subtract, Increment, MultiNot


def test_do_increment_with_no_controls_and_n_dirty():
    backend = DummyEngine(save_commands=True)
    eng = MainEngine(backend=backend, engine_list=[])
    target = eng.allocate_qureg(10)
    dirty = eng.allocate_qureg(10)
    backend.restart_recording()

    do_increment_with_no_controls_and_n_dirty(target, dirty)

    assert backend.received_commands == [
        Subtract.generate_command((dirty, target)),
        MultiNot.generate_command(dirty),
        Subtract.generate_command((dirty, target)),
        MultiNot.generate_command(dirty),
    ]


def test_fuzz_do_increment_with_no_controls_and_n_dirty():
    for _ in range(10):
        fuzz_permutation_circuit(
            register_sizes=[4, 4],
            expected_outs_for_ins=lambda a, b: (a + 1, b),
            engine_list=[AutoReplacer(DecompositionRuleSet(modules=[
                addition_decompositions,
                multi_not_decompositions,
                swap2cnot
            ]))],
            actions=lambda eng, regs:
                do_increment_with_no_controls_and_n_dirty(
                    target_reg=regs[0],
                    dirty_reg=regs[1]))


def test_decomposition_chain():
    backend = DummyEngine(save_commands=True)
    eng = MainEngine(backend=backend, engine_list=[
        AutoReplacer(DecompositionRuleSet(modules=[
            multi_not_decompositions,
            increment_decompositions,
            addition_decompositions,
            swap2cnot,
        ])),
        LimitedCapabilityEngine(allow_toffoli=True),
    ])
    controls = eng.allocate_qureg(40)
    target = eng.allocate_qureg(35)
    _ = eng.allocate_qureg(2)
    Increment & controls | target
    assert 1000 < len(backend.received_commands) < 10000


def test_fuzz_controlled_increment():
    for _ in range(10):
        n = random.randint(1, 30)
        control_size = random.randint(0, 3)
        satisfy = (1 << control_size) - 1
        fuzz_permutation_circuit(
            register_sizes=[control_size, n, 2],
            expected_outs_for_ins=lambda c, t, d:
                (c, t + (1 if c == satisfy else 0), d),
            engine_list=[
                AutoReplacer(DecompositionRuleSet(modules=[
                    swap2cnot,
                    multi_not_decompositions,
                    increment_decompositions,
                    addition_decompositions,
                ])),
                LimitedCapabilityEngine(allow_toffoli=True),
            ],
            actions=lambda eng, regs: Increment & regs[0] | regs[1])
