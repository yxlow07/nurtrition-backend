import pytest
from hackucdbackend.schemas.meal import AIMealAnalysis
from hackucdbackend.schemas.user import DemographicProfile
from hackucdbackend.services.scoring import (
    calculate_raw_score,
    calculate_normalized_score,
    get_score_breakdown,
)


def make_analysis(
    plant_points: int = 30,
    whole_food_points: int = 25,
    protein_points: int = 20,
    upf_penalty: int = 0,
    plant_colors: list = None,
    upf_tier: str = "unprocessed",
    confidence: float = 0.95,
) -> AIMealAnalysis:
    return AIMealAnalysis(
        meal_name="Salmon Rice Bowl",
        detected_ingredients=["salmon", "brown rice", "broccoli", "carrots"],
        plant_colors=plant_colors if plant_colors is not None else ["green", "orange"],
        upf_tier=upf_tier,
        plant_points=plant_points,
        whole_food_points=whole_food_points,
        protein_points=protein_points,
        upf_penalty=upf_penalty,
        confidence=confidence,
        reassurance_note="Great balanced bowl with whole proteins.",
    )


def test_calculate_raw_score():
    analysis = make_analysis(plant_points=30, whole_food_points=20, protein_points=15, upf_penalty=5)
    assert calculate_raw_score(analysis) == 60


def test_student_plant_boost():
    # Student with >= 2 plant colors gets +15% boost
    analysis = make_analysis(
        plant_points=20, whole_food_points=20, protein_points=10, upf_penalty=0,
        plant_colors=["green", "red"]
    )
    # raw = 50. 50 * 1.15 = 57.5 -> 57
    profile = DemographicProfile(age=21, sex="female", activity_level="moderate", role="student")
    assert calculate_normalized_score(analysis, profile) == 57


def test_student_without_plant_diversity():
    # Student with 1 plant color does not get 15% boost
    analysis = make_analysis(
        plant_points=15, whole_food_points=20, protein_points=15, upf_penalty=0,
        plant_colors=["green"]
    )
    # raw = 50. multiplier = 1.0 -> 50
    profile = DemographicProfile(age=21, sex="female", activity_level="moderate", role="student")
    assert calculate_normalized_score(analysis, profile) == 50


def test_parent_upf_penalty():
    # Parent eating ultra processed food gets -15% penalty
    analysis = make_analysis(
        plant_points=10, whole_food_points=10, protein_points=20, upf_penalty=10,
        upf_tier="ultra_processed"
    )
    # raw = 30. multiplier = 0.85 -> 25.5 -> 25
    profile = DemographicProfile(age=52, sex="male", activity_level="sedentary", role="parent")
    assert calculate_normalized_score(analysis, profile) == 25


def test_parent_unprocessed_bonus():
    # Parent eating unprocessed food gets +10% bonus
    analysis = make_analysis(
        plant_points=30, whole_food_points=25, protein_points=15, upf_penalty=0,
        upf_tier="unprocessed"
    )
    # raw = 70. multiplier = 1.10 -> 77
    profile = DemographicProfile(age=50, sex="female", activity_level="moderate", role="parent")
    assert calculate_normalized_score(analysis, profile) == 77


def test_athlete_protein_boost():
    # Athlete with protein points >= 15 gets +10% boost
    analysis = make_analysis(
        plant_points=20, whole_food_points=20, protein_points=20, upf_penalty=0,
        plant_colors=["green"], upf_tier="minimally_processed"
    )
    # raw = 60. multiplier = 1.10 -> 66
    profile = DemographicProfile(age=25, sex="male", activity_level="athlete", role="member")
    assert calculate_normalized_score(analysis, profile) == 66


def test_clamping_bounds():
    # Test lower bound (minimum 10)
    analysis_low = make_analysis(plant_points=0, whole_food_points=0, protein_points=0, upf_penalty=20)
    profile = DemographicProfile(age=30, sex="female", activity_level="sedentary", role="member")
    assert calculate_normalized_score(analysis_low, profile) == 10

    # Test upper bound (maximum 100)
    analysis_high = make_analysis(
        plant_points=50, whole_food_points=30, protein_points=20, upf_penalty=0,
        plant_colors=["green", "red", "orange"], upf_tier="unprocessed"
    )
    profile_student_athlete = DemographicProfile(age=20, sex="female", activity_level="athlete", role="student")
    assert calculate_normalized_score(analysis_high, profile_student_athlete) == 100


def test_get_score_breakdown():
    analysis = make_analysis(plant_points=30, whole_food_points=25, protein_points=20, upf_penalty=0)
    breakdown = get_score_breakdown(analysis)
    assert breakdown == {
        "plant_points": 30,
        "whole_food_points": 25,
        "protein_points": 20,
        "upf_penalty": 0,
        "raw_total": 75,
    }


def test_calculate_score_from_values():
    from hackucdbackend.services.scoring import calculate_score_from_values
    profile = DemographicProfile(age=20, sex="female", activity_level="moderate", role="student")
    raw, norm = calculate_score_from_values(
        plant_points=30,
        whole_food_points=25,
        protein_points=20,
        upf_penalty=0,
        plant_colors=["green", "red"],
        upf_tier="unprocessed",
        profile=profile,
    )
    assert raw == 75
    assert norm == 86  # 75 * 1.15 = 86.25
