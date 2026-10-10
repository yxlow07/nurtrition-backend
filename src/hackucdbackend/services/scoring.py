from typing import Dict
from hackucdbackend.schemas.meal import AIMealAnalysis
from hackucdbackend.schemas.user import DemographicProfile


def calculate_raw_score(analysis: AIMealAnalysis) -> int:
    """Calculate the unweighted raw nutritional score bounded [0, 100]."""
    raw = (
        analysis.plant_points
        + analysis.whole_food_points
        + analysis.protein_points
        - analysis.upf_penalty
    )
    return max(0, min(100, raw))


def calculate_normalized_score(analysis: AIMealAnalysis, profile: DemographicProfile) -> int:
    """Calculate demographic-adjusted score using life-stage multipliers.
    
    Rules:
    - Student: +15% boost if plant diversity >= 2 colors.
    - Parent: -15% penalty if UPF tier in ['processed', 'ultra_processed'],
              +10% boost if UPF tier is 'unprocessed'.
    - Active / Athlete: +10% boost if protein_points >= 15.
    - Result clamped between [10, 100].
    """
    raw = calculate_raw_score(analysis)

    # Weight adjustments based on life-stage demands
    multiplier = 1.0

    if profile.role == "student":
        # Students often suffer plant/micronutrient deficits; boost for plant diversity
        if len(analysis.plant_colors) >= 2:
            multiplier += 0.15
    elif profile.role == "parent":
        # Aging adults benefit from unprocessed diets; penalize UPF more stringently
        if analysis.upf_tier in ["processed", "ultra_processed"]:
            multiplier -= 0.15
        elif analysis.upf_tier == "unprocessed":
            multiplier += 0.10

    if profile.activity_level in ["active", "athlete"] and analysis.protein_points >= 15:
        multiplier += 0.10

    return int(max(10, min(100, raw * multiplier)))


def get_score_breakdown(analysis: AIMealAnalysis) -> Dict[str, int]:
    """Return dictionary of score breakdown for client response."""
    return {
        "plant_points": analysis.plant_points,
        "whole_food_points": analysis.whole_food_points,
        "protein_points": analysis.protein_points,
        "upf_penalty": analysis.upf_penalty,
        "raw_total": calculate_raw_score(analysis),
    }


def calculate_score_from_values(
    plant_points: int,
    whole_food_points: int,
    protein_points: int,
    upf_penalty: int,
    plant_colors: list,
    upf_tier: str,
    profile: DemographicProfile,
) -> tuple[int, int]:
    """Calculate raw and normalized scores directly from values. Returns (raw_score, normalized_score)."""
    raw = plant_points + whole_food_points + protein_points - upf_penalty
    raw = max(0, min(100, raw))

    multiplier = 1.0
    if profile.role == "student":
        if len(plant_colors) >= 2:
            multiplier += 0.15
    elif profile.role == "parent":
        if upf_tier in ["processed", "ultra_processed"]:
            multiplier -= 0.15
        elif upf_tier == "unprocessed":
            multiplier += 0.10

    if profile.activity_level in ["active", "athlete"] and protein_points >= 15:
        multiplier += 0.10

    normalized = int(max(10, min(100, raw * multiplier)))
    return raw, normalized
