# AI-Powered Document Assistant

This project automates the generation of General Offer Arrangement (GOA) documents from PDF quotes using AI. It streamlines sales and manufacturing workflows by intelligently extracting data, populating templates, and tracking modifications.

## Features
- **Automated Data Extraction:** Parses text and tables from PDF quotes and uses a Large Language Model (LLM) to identify key information.
- **Dynamic Document Generation:** Fills `.docx` templates with extracted data.
- **Modification Tracking:** Allows users to modify and regenerate documents while keeping a history of changes.
- **Web Interface:** A user-friendly interface to manage the entire process.

## How It Works

The system uses PDF quotes to populate documents and build a customer database. The workflow extracts data once for use in multiple document types.

```mermaid
flowchart TB
    Start([User Uploads PDF Quote]) --> Extract[Extract Data from PDF]

    Extract --> ParseItems[Parse Line Items & Details]
    Extract --> ExtractText[Extract Full Text]

    ParseItems --> IdentifyMachines[Identify Machines]
    IdentifyMachines --> GroupItems[Group Items by Machine]

    GroupItems --> CreateClient{New or Existing Client?}

    CreateClient -->|New Client| SaveNewClient[Create Client Record]
    CreateClient -->|Existing Client| LinkQuote[Link Quote to Client]

    SaveNewClient --> SaveToDB[(Save to Database)]
    LinkQuote --> SaveToDB

    SaveToDB --> SaveItems[Save Line Items]
    SaveItems --> SaveMachines[Save Machine Data]
    SaveMachines --> SaveDoc[Save Document Content]
    ExtractText --> SaveDoc

    SaveDoc --> UserChoice{User Action}

    UserChoice -->|Generate GOA| SelectMachine[Select Machine]
    UserChoice -->|Build Reports| BuildReports[Machine Build Summary]
    UserChoice -->|Chat with Document| ChatInterface[Open Chat Interface]
    UserChoice -->|Modify Templates| ModifyUI[Template Modification UI]

    %% Future items (dotted connectors)
    UserChoice -.->|Future: Packing Slip| GenPacking[Generate Packing Document]
    UserChoice -.->|Future: Invoice| GenInvoice[Generate Commercial Invoice]
    UserChoice -.->|Future: COO| GenCOO[Generate Certificate of Origin]

    SelectMachine --> DetectType{Machine Type?}
    DetectType -->|Regular Machine| LoadTemplate1[Load Standard Template]
    DetectType -->|SortStar Machine| LoadTemplate2[Load SortStar Template]

    LoadTemplate1 --> LLMProcess[LLM Processes Data]
    LoadTemplate2 --> LLMProcess

    LLMProcess --> FillTemplate[Fill Template Fields]
    FillTemplate --> GenerateOptions[Generate Options Listing]
    GenerateOptions --> SaveTemplate[(Save Template Data)]

    SaveTemplate --> GenerateDoc[Generate Word Document]
    GenerateDoc --> Download[User Downloads Document]

    BuildReports --> SelectTemplate[Select GOA Template]
    SelectTemplate --> GenerateSummary[Generate Summary Report]
    GenerateSummary --> Download

    ModifyUI --> LoadSaved[Load Saved Templates]
    LoadSaved --> EditFields[Edit Field Values]
    EditFields --> SaveMods[(Save Modifications)]
    SaveMods --> RegenerateDoc[Regenerate Document]
    RegenerateDoc --> Download

    ChatInterface --> QueryLLM[Query LLM with Context]
    QueryLLM --> ShowResponse[Display Response]

    GenPacking -.-> Download
    GenInvoice -.-> Download
    GenCOO -.-> Download

    %% Styles (keep them conservative for mermaid.live)
    style Start fill:#e1f5fe,stroke:#4FC3F7
    style SaveToDB fill:#fff3e0,stroke:#FFB74D
    style Download fill:#c8e6c9,stroke:#81C784
    style LLMProcess fill:#f3e5f5,stroke:#BA68C8
    %% If dashed borders are needed, use a class:
    classDef future stroke:#999,stroke-width:1px;
    class GenPacking,GenInvoice,GenCOO future;
```

## Getting Started

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Set Environment Variables:**
    Create a `.env` file and add your `GOOGLE_API_KEY`.
3.  **Initialize Database:**
    ```bash
    python initialize_db.py
    ```
4.  **Run the App:**
    ```bash
    streamlit run app.py
    ```