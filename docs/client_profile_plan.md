# Client Profile Workflow Implementation Plan

## Objective
Create a workflow that first extracts client profile information from uploaded quotes, then allows users to select from various actions to perform with that profile.

## Implementation Steps

### 1. Client Profile Extraction
- Extract client information from uploaded PDF
- Use LLM to identify key client fields (name, contact, addresses)
- Extract quote metadata (reference, date)
- Extract line items and identify machines

### 2. Profile Confirmation UI
- Display extracted client information
- Allow editing/confirmation of client details
- Show summary of identified machines/line items
- Save confirmed profile to database

### 3. Action Selection Hub
- Present card-based UI for selecting actions
- Options include: GOA generation, export documents, edit profile, chat with quote
- Make selection UI the central navigation point

### 4. Integration with Existing Functionality
- Connect profile data to document generation functions
- Ensure profile data is used for export documents
- Maintain backward compatibility with existing features

## New Functions to Create
1. `extract_client_profile(pdf_path)`
2. `confirm_client_profile(extracted_profile)`
3. `show_action_selection(client_profile)`
4. `handle_selected_action(action, profile_data)`

## UI Flow
1. Upload PDF → Extract Profile → Confirm Profile → Action Selection Hub
2. From Hub → Selected Action → Return to Hub

## Database Updates
- Add timestamps for profile creation/updates
- Add action history for each client profile
- Link documents generated to specific profile versions 