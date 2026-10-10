# FamilyCareEats API Documentation & Frontend Integration Guide

This document contains complete API specifications, data contracts, and code snippets for integrating mobile (React Native / Expo) and web frontend clients with the **FamilyCareEats** backend service.

---

## 1. General Architecture & Base Configuration

### Base URL
- **API Base URL:** `https://wheatless-jermaine-aftmost.ngrok-free.dev`
- **Interactive Swagger UI:** `https://wheatless-jermaine-aftmost.ngrok-free.dev/docs`
- **Alternative ReDoc UI:** `https://wheatless-jermaine-aftmost.ngrok-free.dev/redoc`

### Standard Headers
```http
Content-Type: application/json
Accept: application/json
```

### Authentication Scheme
All protected endpoints require the standard JWT Bearer token:
```http
Authorization: Bearer <YOUR_ACCESS_TOKEN>
```
*(During development/testing, passing `X-User-Id: <UUID>` is also accepted).*

---

## 2. Authentication & Profile Endpoints

### 2.1 Register User
- **Endpoint:** `POST /api/v1/auth/register`
- **Auth Required:** No

#### Request Body
```json
{
  "email": "sarah.student@university.edu",
  "password": "strongPassword123",
  "full_name": "Sarah Miller",
  "role": "student",
  "age": 20,
  "sex": "female",
  "activity_level": "moderate",
  "dietary_flags": ["vegetarian", "halal"]
}
```

| Field | Type | Rules & Allowed Values | Description |
| :--- | :--- | :--- | :--- |
| `email` | `string` | Valid email, min 5 chars, unique | Login identifier |
| `password` | `string` | Min 6 characters | Plain text password (hashed via PBKDF2) |
| `full_name` | `string` | Min 1, max 100 chars | Display name |
| `role` | `string` | `"student"` \| `"parent"` \| `"member"` | Controls demographic scoring rules |
| `age` | `integer` | 1 – 120 | Demographic age |
| `sex` | `string` | `"male"` \| `"female"` \| `"other"` | Biological sex |
| `activity_level`| `string` | `"sedentary"` \| `"moderate"` \| `"active"` \| `"athlete"` | Daily exercise level |
| `dietary_flags` | `string[]`| Optional array of strings (e.g. `["halal"]`) | Dietary restrictions |

#### Response (`201 Created`)
```json
{
  "user": {
    "id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
    "email": "sarah.student@university.edu",
    "full_name": "Sarah Miller",
    "role": "student",
    "age": 20,
    "sex": "female",
    "activity_level": "moderate",
    "dietary_flags": ["vegetarian", "halal"],
    "created_at": "2026-10-10T12:00:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### 2.2 Login User
- **Endpoint:** `POST /api/v1/auth/login`
- **Auth Required:** No

#### Request Body
```json
{
  "email": "sarah.student@university.edu",
  "password": "strongPassword123"
}
```

#### Response (`200 OK`)
```json
{
  "user": {
    "id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
    "email": "sarah.student@university.edu",
    "full_name": "Sarah Miller",
    "role": "student",
    "age": 20,
    "sex": "female",
    "activity_level": "moderate",
    "dietary_flags": ["vegetarian", "halal"],
    "created_at": "2026-10-10T12:00:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Error Response (`401 Unauthorized`)
```json
{
  "detail": "Invalid email or password"
}
```

---

### 2.3 Get Current User Profile (`Me`)
- **Endpoint:** `GET /api/v1/users/me`
- **Auth Required:** Yes (`Bearer <token>`)

#### Response (`200 OK`)
```json
{
  "id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
  "email": "sarah.student@university.edu",
  "full_name": "Sarah Miller",
  "profile": {
    "age": 20,
    "sex": "female",
    "activity_level": "moderate",
    "role": "student"
  },
  "dietary_flags": ["vegetarian", "halal"],
  "family_id": "4b68e980-60b1-477f-a630-f38b16bbd405",
  "created_at": "2026-10-10T12:00:00Z"
}
```
*(Note: `family_id` will be `null` if user has not yet created or joined a family).*

---

## 3. Meal Ingestion & Reaction Endpoints

### 3.1 Upload Meal Photo & Instant Analysis
- **Endpoint:** `POST /api/v1/meals/upload`
- **Auth Required:** Yes (`Bearer <token>`)
- **Content-Type:** `multipart/form-data`

#### Multipart Form Fields
| Field Name | Type | Required | Values / Notes |
| :--- | :--- | :--- | :--- |
| `image` | `Binary File` | **Yes** | JPEG, PNG, or WebP (max 10MB; recommend resizing to max dimension 1024px) |
| `preparation_context` | `string` | No (default `"home_cooked"`) | `"home_cooked"` \| `"takeout"` \| `"dining_hall"` \| `"packaged"` |
| `family_id` | `UUID` | No | Target family circle UUID. If omitted, uses user's active family circle. |

#### Response (`201 Created`)
```json
{
  "meal_id": "8d3e2304-4b51-4043-982f-897b5e408ec9",
  "image_url": "https://mzerjfdyquxnrlmlzybl.supabase.co/storage/v1/object/public/meals/7d9b7f58-.../8d3e2304-....jpg",
  "meal_name": "Stir-fried Tofu with Broccoli and Brown Rice",
  "scores": {
    "plant_points": 30,
    "whole_food_points": 25,
    "protein_points": 20,
    "upf_penalty": 0,
    "raw_total": 75
  },
  "normalized_score": 86,
  "reassurance_note": "Nutrient-dense dinner rich in plant protein, dietary fiber, and dark greens.",
  "plant_colors": ["green", "orange"],
  "created_at": "2026-10-10T12:05:00Z"
}
```

> **Client UI Guidance:**
> - Display `normalized_score` (out of 100) prominently on the meal card.
> - Render `plant_colors` as colored badge tags (e.g., green, orange, red, purple, yellow_white).
> - Present `reassurance_note` as the warm, supportive summary banner.

---

### 3.2 Get Meal Audit Breakdown
- **Endpoint:** `GET /api/v1/meals/{meal_id}`
- **Auth Required:** Yes (`Bearer <token>`)

#### Response (`200 OK`)
```json
{
  "id": "8d3e2304-4b51-4043-982f-897b5e408ec9",
  "user_id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
  "family_id": "4b68e980-60b1-477f-a630-f38b16bbd405",
  "image_url": "https://mzerjfdyquxnrlmlzybl.supabase.co/storage/v1/object/public/meals/...",
  "preparation_context": "home_cooked",
  "meal_name": "Stir-fried Tofu with Broccoli and Brown Rice",
  "detected_ingredients": ["tofu", "broccoli", "brown rice", "carrots"],
  "plant_colors": ["green", "orange"],
  "upf_tier": "unprocessed",
  "plant_score": 30,
  "whole_food_score": 25,
  "protein_score": 20,
  "penalty_score": 0,
  "raw_score": 75,
  "normalized_score": 86,
  "reassurance_note": "Nutrient-dense dinner rich in plant protein, dietary fiber, and dark greens.",
  "ai_confidence": 0.94,
  "requires_manual_tags": false,
  "reactions": ["❤️", "🥦"],
  "created_at": "2026-10-10T12:05:00Z"
}
```

---

### 3.3 1-Tap Reaction Toggle
- **Endpoint:** `POST /api/v1/meals/{meal_id}/react`
- **Auth Required:** Yes (`Bearer <token>`)

#### Request Body
```json
{
  "emoji": "❤️"
}
```

#### Response (`200 OK`)
```json
{
  "action": "added",
  "emoji": "❤️",
  "reactions": ["❤️", "🥦"]
}
```
*(If the user taps the same emoji again, `"action": "removed"` is returned and that emoji is removed from `"reactions"`).*

---

## 4. Family Circles & Social Feed Endpoints

### 4.1 Create Family Circle
- **Endpoint:** `POST /api/v1/families/create`
- **Auth Required:** Yes (`Bearer <token>`)

#### Request Body
```json
{
  "name": "The Miller Family"
}
```

#### Response (`201 Created`)
```json
{
  "id": "4b68e980-60b1-477f-a630-f38b16bbd405",
  "name": "The Miller Family",
  "invite_code": "MILLER48",
  "members": [
    {
      "user_id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
      "full_name": "Sarah Miller",
      "role": "student",
      "joined_at": "2026-10-10T12:00:00Z"
    }
  ],
  "created_at": "2026-10-10T12:00:00Z"
}
```

---

### 4.2 Join Family Circle via Invite Code
- **Endpoint:** `POST /api/v1/families/join`
- **Auth Required:** Yes (`Bearer <token>`)

#### Request Body
```json
{
  "invite_code": "MILLER48"
}
```

#### Response (`200 OK`)
```json
{
  "id": "4b68e980-60b1-477f-a630-f38b16bbd405",
  "name": "The Miller Family",
  "invite_code": "MILLER48",
  "members": [
    {
      "user_id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
      "full_name": "Sarah Miller",
      "role": "student",
      "joined_at": "2026-10-10T12:00:00Z"
    },
    {
      "user_id": "9a12c833-28da-43bc-9171-89304aef729a",
      "full_name": "Mark Miller",
      "role": "parent",
      "joined_at": "2026-10-10T12:15:00Z"
    }
  ],
  "created_at": "2026-10-10T12:00:00Z"
}
```

---

### 4.3 Get Family Timeline Feed
- **Endpoint:** `GET /api/v1/families/{family_id}/feed`
- **Auth Required:** Yes (`Bearer <token>`)
- **Query Parameters:**
  - `limit`: Integer, default `20`, max `100`
  - `offset`: Integer, default `0`

#### Response (`200 OK`)
```json
[
  {
    "meal_id": "8d3e2304-4b51-4043-982f-897b5e408ec9",
    "user_name": "Sarah Miller",
    "user_role": "student",
    "image_url": "https://mzerjfdyquxnrlmlzybl.supabase.co/storage/v1/object/public/meals/...",
    "meal_name": "Stir-fried Tofu with Broccoli and Brown Rice",
    "normalized_score": 86,
    "plant_colors": ["green", "orange"],
    "reassurance_note": "Nutrient-dense dinner rich in plant protein, dietary fiber, and dark greens.",
    "reactions": ["❤️", "🥦"],
    "created_at": "2026-10-10T12:05:00Z"
  }
]
```

---

### 4.4 Get Weekly Family Digest & Leaderboard
- **Endpoint:** `GET /api/v1/families/{family_id}/weekly`
- **Auth Required:** Yes (`Bearer <token>`)
- **Query Parameters:**
  - `force_refresh`: Boolean, default `false` *(Set `true` if you wish to re-synthesize the AI narrative)*

#### Response (`200 OK`)
```json
{
  "id": "e84e2098-b80c-4fa2-bf41-2a1f185f4019",
  "family_id": "4b68e980-60b1-477f-a630-f38b16bbd405",
  "week_start": "2026-10-05",
  "week_end": "2026-10-11",
  "leaderboard_payload": {
    "total_meals": 14,
    "rankings": [
      {
        "user_id": "7d9b7f58-5c4b-4c07-9bfa-f6f7ab1829e1",
        "full_name": "Sarah Miller",
        "role": "student",
        "meal_count": 8,
        "total_score": 672,
        "avg_score": 84.0,
        "plant_diversity_count": 4,
        "plant_colors": ["green", "orange", "red", "yellow_white"],
        "top_meal": "Stir-fried Tofu with Broccoli and Brown Rice"
      },
      {
        "user_id": "9a12c833-28da-43bc-9171-89304aef729a",
        "full_name": "Mark Miller",
        "role": "parent",
        "meal_count": 6,
        "total_score": 456,
        "avg_score": 76.0,
        "plant_diversity_count": 3,
        "plant_colors": ["green", "red", "yellow_white"],
        "top_meal": "Grilled Salmon and Steamed Greens"
      }
    ]
  },
  "collective_plant_count": 4,
  "ai_family_narrative": "The Miller family enjoyed a vibrant week of shared meals, reaching 4 botanical color categories across 14 plates! Consistency in whole grains and fresh greens stood out as a highlight.",
  "recommended_grocery_swap": "Try replacing regular white pasta with chickpea or lentil pasta for an extra 12g of plant protein and 6g of fiber per serving.",
  "created_at": "2026-10-10T12:00:00Z"
}
```

---

## 5. Mobile Client Code Snippets (React Native / Expo)

### 5.1 Uploading Meal Photo with `FormData`
```typescript
import * as ImagePicker from 'expo-image-picker';

export async function uploadMealPhoto(token: string, familyId?: string) {
  // 1. Pick or capture photo
  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.8,
  });

  if (result.canceled) return null;
  const asset = result.assets[0];

  // 2. Prepare FormData
  const formData = new FormData();
  formData.append('image', {
    uri: asset.uri,
    name: 'meal_photo.jpg',
    type: 'image/jpeg',
  } as any);

  formData.append('preparation_context', 'home_cooked');
  if (familyId) {
    formData.append('family_id', familyId);
  }

  // 3. Dispatch upload
  const API_BASE_URL = 'https://wheatless-jermaine-aftmost.ngrok-free.dev';
  const response = await fetch(`${API_BASE_URL}/api/v1/meals/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      // Note: Do NOT set Content-Type manually when using FormData in React Native
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }

  return await response.json();
}
```

### 5.2 1-Tap Reaction Handler
```typescript
export async function toggleReaction(mealId: string, emoji: string, token: string) {
  const API_BASE_URL = 'https://wheatless-jermaine-aftmost.ngrok-free.dev';
  const response = await fetch(`${API_BASE_URL}/api/v1/meals/${mealId}/react`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ emoji }),
  });

  return await response.json(); // { action: "added" | "removed", reactions: [...] }
}
```

---

## 6. HTTP Status Codes & Error Format

All error responses return a standardized JSON error payload:
```json
{
  "detail": "Description of what went wrong"
}
```

| Status Code | Meaning | Common Scenario |
| :--- | :--- | :--- |
| `200 OK` | Success | Successful read / update / login |
| `201 Created` | Resource Created | Successful register / upload / family create |
| `400 Bad Request` | Client Input Error | Duplicate email, file empty, or invalid mime type |
| `401 Unauthorized` | Invalid / Missing Auth | Invalid password or expired Bearer token |
| `404 Not Found` | Resource Missing | Non-existent meal ID or invalid family invite code |
| `413 Payload Too Large`| File Exceeds Size | Photo file exceeds 10MB limit |
| `422 Unprocessable` | Schema Validation Error | Missing required field or invalid enum string |
| `502 Bad Gateway` | Upstream AI Gateway | OpenRouter outage (fallback model will be attempted automatically) |
