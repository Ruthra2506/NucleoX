# NucleoX — On-Spot DNA Analysis System

> **Portable DNA Processing Device Software Layer**  
> *Student / Hackathon Prototype — Synthetic Data for Demonstration Purposes Only*

---

## 🧬 Overview

**NucleoX** is the web application and monitoring software layer for a portable, on-spot DNA processing hardware prototype powered by ESP32 micro-controllers. It provides end-to-end evidence intake, reference sample management, real-time PCR thermal thermocycling ingestion over USB serial, a 5-stage simulated Short Tandem Repeat (STR) profiling pipeline with electropherogram peak visualization, locus-by-locus profile comparison, printable forensic reports, and a SHA-256 blockchain-backed digital chain-of-custody audit ledger.

---

## 🚀 Key Modules & Architecture

### Module 1: Evidence Registration
- Auto-generates sequential Evidence IDs (`E001`, `E002`, ...).
- Form inputs: Sample Type (Blood, Saliva, Hair, Touch DNA, Tissue, Buccal Swab), Operator ID, Collection Timestamp.
- Automatically inserts into `samples` SQLite table and appends a `Collected` block to the blockchain custody ledger.

### Module 2: Reference Sample Registration (NEW)
- Purpose: Registers known reference samples (Suspect, Victim, Elimination, Known Individual) to enable comparison of evidence profiles against known sources.
- Auto-generates Reference IDs (`R001`, `R002`, ...).
- Form inputs: Source Type dropdown, Subject Label (synthetic e.g. "Suspect Alpha"), Operator ID, Collection Timestamp.
- Inserts into `reference_samples` SQLite table and appends a `Collected` block tagged `sample_ref_type = 'Reference'`.

### Module 3: Device Monitoring (PCR Thermal Telemetry)
- `hardware.py` receives live serial telemetry from the ESP32 thermocycler over USB serial.
- Includes a non-blocking background thread simulator for offline hackathon demos (30 PCR thermal cycles: Denaturation 95°C → Annealing 55°C → Extension 72°C).
- Writes real-time temperature, cycle number, progress %, and run status to `pcr_runs`.
- Emits `PCR started` and `PCR completed` blocks to the custody blockchain when thermal cycling reaches 100%.

### Module 4: STR Profiling Simulation (EXPANDED)
- Executes a 5-stage visible sequence:
  1. **DNA Extraction** — instant timestamped step
  2. **PCR Amplification** — summarizes thermal cycling telemetry
  3. **Capillary Electrophoresis** — generates synthetic electropherogram peak data (base-pair position + RFU fluorescence height) per locus
  4. **Allele Calling** — deterministically derives 5 STR locus allele pairs (`TH01`, `vWA`, `TPOX`, `CSF1PO`, `D16S539`) using deterministic MD5 hash seeding per sample ID
  5. **Profile Generated** — stores row in `profiles` table and appends a `Result stored` custody block to the blockchain ledger
- Renders simulated electropherogram peak bar charts and allele call tables with mandatory demonstration disclaimers.

### Module 5: Blockchain-Backed Chain of Custody (EXPANDED)
- Implements an append-only, SHA-256 hash-linked ledger in `custody_blocks` (`blockchain.py`).
- Each custody event creates a block containing:
  - `block_index`: Sequential block integer
  - `sample_ref_id`: Evidence or Reference sample ID
  - `sample_ref_type`: `'Evidence'` or `'Reference'`
  - `event_name`: Description of event
  - `event_timestamp`: Timestamp
  - `data_hash`: `SHA-256(block_index|sample_ref_id|sample_ref_type|event_name|event_timestamp)`
  - `previous_hash`: `block_hash` of preceding block (`"0"` for genesis block)
  - `block_hash`: `SHA-256(data_hash|previous_hash)`
- Includes an interactive **Verify Chain Integrity** engine that recomputes every block's hashes from genesis to confirm the chain is unbroken and untampered.

### Module 6: Profile Comparison (EXPANDED)
- Two selector dropdowns allow comparing any two profiled samples (Evidence vs Evidence or Evidence vs Reference).
- Performs locus-by-locus matching across all 5 loci.
- Overall result: `CONSISTENT` (100% locus match), `DIFFERENT` (at least 1 mismatch), or `INCONCLUSIVE` (if profile data is incomplete).
- Saves results to `comparisons` table and appends a `Compared` custody block for both samples involved.

### Module 7: Dashboard (Home Page)
- Features a splash screen loading overlay on first visit.
- Displays summary metric cards (Evidence count, Reference count, Active PCR runs, DNA Profiles).
- Renders two distinct inventory tables: Crime Scene Evidence Samples and Known Reference Samples.

### Module 8: Printable Forensic Report
- Generates a printable report containing NucleoX header branding, sample demographics, PCR thermal run metrics, 5-stage STR pipeline steps, profile allele table, comparison history, complete blockchain custody timeline, and chain integrity verification badge.

---

## 🗄️ Database Schema (SQLite — 7 Tables)

1. `samples` (`evidence_id`, `sample_type`, `operator`, `collection_time`, `status`)
2. `reference_samples` (`reference_id`, `source_type`, `subject_label`, `operator`, `collection_time`, `status`)
3. `pcr_runs` (`id`, `sample_ref_id`, `sample_ref_type`, `timestamp`, `temperature`, `cycle_number`, `progress_percent`, `run_status`)
4. `str_profiling_runs` (`id`, `sample_ref_id`, `sample_ref_type`, `stage`, `stage_status`, `timestamp`)
5. `profiles` (`sample_ref_id`, `sample_ref_type`, `locus_1`, `locus_2`, `locus_3`, `locus_4`, `locus_5`, `generated_at`)
6. `custody_blocks` (`id`, `block_index`, `sample_ref_id`, `sample_ref_type`, `event_name`, `event_timestamp`, `data_hash`, `previous_hash`, `block_hash`)
7. `comparisons` (`id`, `evidence_id`, `reference_id_or_evidence_id_2`, `result`, `compared_at`)

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- `pip` package manager

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Application
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔌 ESP32 Serial Port Configuration

If connecting physical ESP32 hardware:
1. Connect ESP32 via USB.
2. Identify the COM port (Windows: `COM3`, `COM4`; Linux/Mac: `/dev/ttyUSB0` or `/dev/ttyACM0`).
3. Navigate to **Run Device** (`/device`), select your port from the **ESP32 Hardware USB Serial Port** dropdown, and click **Start PCR Thermal Run**.
4. Format expected over serial from ESP32:
   ```json
   {"sample_ref_id": "E001", "type": "Evidence", "temp": 95.2, "cycle": 1, "progress": 3.3, "status": "Running"}
   ```
   *(If no hardware is connected, NucleoX automatically falls back to the built-in non-blocking hardware simulator).*

---

## 🧪 Running Automated Unit Tests

To run the complete automated test suite testing DB tables, registration, STR simulation, profile comparison, blockchain hashing, and Flask routes:

```bash
python test_nucleox.py
```

---

## ⚖️ Forensic & Demonstration Disclaimer
*All DNA profiles, allele calls, electropherogram peak values, subject labels, and comparison results generated by NucleoX are 100% synthetic placeholder data designed exclusively for student demonstration and hackathon presentations.*
