-- ============================================================
-- FamilyCareEats Database Schema for Supabase (PostgreSQL)
-- Schema: public
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users & Demographic Profiles
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('student', 'parent', 'member')),
    age INT NOT NULL,
    sex VARCHAR(20) NOT NULL CHECK (sex IN ('male', 'female', 'other')),
    activity_level VARCHAR(30) DEFAULT 'moderate' CHECK (activity_level IN ('sedentary', 'moderate', 'active', 'athlete')),
    dietary_flags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Family Circles
CREATE TABLE IF NOT EXISTS public.family_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    invite_code VARCHAR(8) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.family_members (
    family_id UUID REFERENCES public.family_groups(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (family_id, user_id)
);

-- 3. Meal Logs & AI Output
CREATE TABLE IF NOT EXISTS public.meals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    family_id UUID REFERENCES public.family_groups(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    preparation_context VARCHAR(30) DEFAULT 'home_cooked' CHECK (preparation_context IN ('home_cooked', 'takeout', 'dining_hall', 'packaged')),
    meal_name VARCHAR(150),
    detected_ingredients TEXT[] DEFAULT '{}',
    plant_colors TEXT[] DEFAULT '{}',
    upf_tier VARCHAR(30) CHECK (upf_tier IN ('unprocessed', 'minimally_processed', 'processed', 'ultra_processed')),
    plant_score INT NOT NULL DEFAULT 0,
    whole_food_score INT NOT NULL DEFAULT 0,
    protein_score INT NOT NULL DEFAULT 0,
    penalty_score INT NOT NULL DEFAULT 0,
    raw_score INT NOT NULL DEFAULT 0,
    normalized_score INT NOT NULL DEFAULT 0,
    reassurance_note TEXT,
    ai_confidence NUMERIC(3, 2),
    requires_manual_tags BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Social Reactions
CREATE TABLE IF NOT EXISTS public.meal_reactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meal_id UUID REFERENCES public.meals(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    emoji VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(meal_id, user_id, emoji)
);

-- 5. Weekly Family Digests
CREATE TABLE IF NOT EXISTS public.weekly_digests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    family_id UUID REFERENCES public.family_groups(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    leaderboard_payload JSONB NOT NULL,
    collective_plant_count INT NOT NULL DEFAULT 0,
    ai_family_narrative TEXT NOT NULL,
    recommended_grocery_swap TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_meals_family_created ON public.meals(family_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meals_user_created ON public.meals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meal_reactions_meal ON public.meal_reactions(meal_id);
CREATE INDEX IF NOT EXISTS idx_weekly_digests_family ON public.weekly_digests(family_id, week_start, week_end);

-- ============================================================
-- Supabase Storage RLS Policies for 'meals' bucket
-- ============================================================

-- Allow uploads (INSERT) to the 'meals' bucket
CREATE POLICY "Allow public upload to meals bucket"
ON storage.objects FOR INSERT TO anon, authenticated
WITH CHECK (bucket_id = 'meals');

-- Allow reads (SELECT) from the 'meals' bucket
CREATE POLICY "Allow public read from meals bucket"
ON storage.objects FOR SELECT TO anon, authenticated
USING (bucket_id = 'meals');
