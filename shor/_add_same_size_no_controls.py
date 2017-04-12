# -*- coding: utf-8 -*-
from projectq.cengines import DecompositionRuleSet, DecompositionRule

from projectq.meta import Dagger

from projectq.ops import X, Swap, All, C, BasicGate, NotMergeable, Command


def do_addition_with_same_size_and_no_controls(eng, input_reg, target_reg):
    """
    Reversibly subtracts one register out of another of the same size.

    N: len(input_reg) + len(target_ref)
    Size: O(N)
    Depth: O(N)

    Sources:
        Takahashi and Kunihiro, 2005
        "A linear-size quantum circuit for addition with no ancillary qubits"

        Yvan Van Rentergem and Alexis De Vos, 2004
        "Optimal Design of A Reversible Full Adder"

    Diagram:
       ┌───┐
       ┤   ├       ─⊕─────×─────────────────────────────────────×─●───⊕─
       │   │        │     │                                     │ │   │
       ┤   ├       ─⊕─────┼────×───────────────────────────×─●──┼─┼───⊕─
       │   │        │     │    │                           │ │  │ │   │
       ┤inp├       ─⊕─────┼────┼────×─────────────────×─●──┼─┼──┼─┼───⊕─
       │ A │        │     │    │    │                 │ │  │ │  │ │   │
       ┤   ├       ─⊕─────┼────┼────┼────×───────×─●──┼─┼──┼─┼──┼─┼───⊕─
       │   │        │     │    │    │    │       │ │  │ │  │ │  │ │   │
       ┤   ├       ─●───●─×──●─×──●─×──●─×───●───×─┼──×─┼──×─┼──×─┼───●─
       └─┬─┘        │   │ │  │ │  │ │  │ │   │   │ │  │ │  │ │  │ │   │
       ┌─┴─┐   =    │   │ │  │ │  │ │  │ │   │   │ │  │ │  │ │  │ │   │
       ┤   ├       ─⊕───⊕─●──┼─●──┼─┼──┼─┼───┼───┼─┼──┼─┼──┼─┼──●─⊕───⊕─
       │   │        │        │ │  │ │  │ │   │   │ │  │ │  │ │        │
       ┤   ├       ─⊕────────⊕─●──┼─┼──┼─┼───┼───┼─┼──┼─┼──●─⊕────────⊕─
       │   │        │             │ │  │ │   │   │ │  │ │             │
       ┤+=A├       ─⊕─────────────⊕─●──┼─┼───┼───┼─┼──●─⊕─────────────⊕─
       │   │        │                  │ │   │   │ │                  │
       ┤   ├       ─⊕──────────────────⊕─●───┼───●─⊕──────────────────⊕─
       │   │        │                        │                        │
       ┤   ├       ─⊕────────────────────────⊕────────────────────────⊕─
       └───┘
                   (1)  --------(2)-------  (3)  --------(4)-------  (5)
    Args:
        eng (projectq.cengines.BasicEngine): Engine.
        input_reg (projectq.types.Qureg):
            The source register. Used as workspace, but ultimately not affected
            by the operation.
            end.
        target_reg (projectq.types.Qureg):
            The destination register, whose value is increased by the value in
            the source register.
    """
    assert len(input_reg) == len(target_reg)
    n = len(target_reg)
    if n == 0:
        return

    carry_bit = input_reg[-1]
    cnot = C(X)
    cnots = C(All(X))
    cswap = C(Swap)

    # (1) Dirty MSB correction.
    cnots | (carry_bit, (input_reg[:-1] + target_reg)[::-1])

    # (2) Ripple forward.
    for i in range(n - 1):
        cnot | (carry_bit, target_reg[i])
        cswap | (target_reg[i], carry_bit, input_reg[i])

    # (3) High bit toggle.
    cnot | (carry_bit, target_reg[-1])

    # (4) Ripple backward.
    for i in range(n - 1)[::-1]:
        cswap | (target_reg[i], carry_bit, input_reg[i])
        cnot | (input_reg[i], target_reg[i])

    # (5) Dirty MSB correction.
    cnots | (carry_bit, input_reg[:-1] + target_reg)


def do_addition_no_controls(eng, input_reg, target_reg):
    # When input is larger, just ignore its high bits.
    if len(input_reg) >= len(target_reg):
        do_addition_no_controls(eng, input_reg[:len(target_reg)], target_reg)
        return

    # When target is larger, need to get fancier.
    raise NotImplementedError()


def do_addition(eng, input_reg, target_reg, dirty, controls):
    if len(controls) == 0:
        return do_addition_no_controls(eng, input_reg, target_reg)

    # Remove controls with double-add-invert trick.
    expanded = [dirty] + target_reg
    for _ in range(2):
        do_addition_no_controls(eng, input_reg, expanded)
        C(All(X), len(controls)) | (controls, expanded)
        All(X) | expanded


def do_subtraction(eng, input_reg, target_reg, dirty, controls):
    with Dagger(eng):
        do_addition(eng, input_reg, target_reg, dirty, controls)


def do_subtraction_no_controls(eng, input_reg, target_reg):
    with Dagger(eng):
        do_addition_no_controls(eng, input_reg, target_reg)


class AdditionGate(BasicGate):
    def get_inverse(self):
        return SubtractionGate()

    def get_merged(self, other):
        raise NotMergeable("BasicGate: No get_merged() implemented.")


class SubtractionGate(BasicGate):
    def get_inverse(self):
        return AdditionGate()

    def get_merged(self, other):
        raise NotMergeable("BasicGate: No get_merged() implemented.")


all_defined_decomposition_rules = [
    DecompositionRule(
        gate_class=AdditionGate,
        gate_decomposer=lambda cmd: do_addition(
            cmd.eng,
            input_reg=cmd.qubits[0],
            target_reg=cmd.qubits[1],
            controls=cmd.control_qubits,
            dirty=cmd.untouched_qubits()[0]),
        allocated_but_untouched_bits_required=1),

    DecompositionRule(
        gate_class=AdditionGate,
        gate_decomposer=lambda cmd: do_addition_no_controls(
            cmd.eng,
            input_reg=cmd.qubits[0],
            target_reg=cmd.qubits[1]),
        max_controls=0),

    DecompositionRule(
        gate_class=SubtractionGate,
        gate_decomposer=lambda cmd: do_subtraction(
            cmd.eng,
            input_reg=cmd.qubits[0],
            target_reg=cmd.qubits[1],
            controls=cmd.control_qubits,
            dirty=cmd.untouched_qubits()[0]),
        allocated_but_untouched_bits_required=1),

    DecompositionRule(
        gate_class=SubtractionGate,
        gate_decomposer=lambda cmd: do_subtraction_no_controls(
            cmd.eng,
            input_reg=cmd.qubits[0],
            target_reg=cmd.qubits[1]),
        max_controls=0),
]
