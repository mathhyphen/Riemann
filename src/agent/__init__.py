"""Riemann Agent - Mathematical Proof Verification Agent.

This module provides the core agent logic for:
- Proof generation using LLM
- Conversion of natural language proofs to Lean 4 code
- Verification loop with iterative refinement
- Mathlib theorem retrieval
- Proof explanation
"""

from .state import AgentContext, AgentConfig, ProofState
from .proof_generator import ProofGenerator
from .proof_to_lean import ProofToLeanConverter
from .verification_loop import VerificationLoop
from .mathlib_retriever import MathlibRetriever, MathlibTheoremHit
from .proof_explainer import ProofExplainer

__all__ = [
    "AgentContext",
    "AgentConfig",
    "ProofState",
    "ProofGenerator",
    "ProofToLeanConverter",
    "VerificationLoop",
    "MathlibRetriever",
    "MathlibTheoremHit",
    "ProofExplainer",
]
