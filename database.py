"""
NucleoX - SQLite Database Management Layer
Provides schema initialization for all 7 SQLite tables and CRUD operations for:
1. samples (Evidence samples)
2. reference_samples (Reference/Known samples)
3. pcr_runs (Hardware thermal telemetry)
4. str_profiling_runs (5-stage STR pipeline execution tracking)
5. profiles (5-locus STR DNA profiles)
6. custody_blocks (SHA-256 hash-chain custody ledger)
7. comparisons (Locus comparison results)
"""

import sqlite3
import os
from datetime import datetime
import blockchain

DB_PATH = os.path.join(os.path.dirname(__file__), 'nucleox.db')

def get_db_connection():
    """Returns a connection to the SQLite database with Row factory enabled and 30s timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    """
    Initializes SQLite database schema creating all 7 required tables.
    Populates realistic seed demo data if database is empty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: samples (Evidence samples)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS samples (
            evidence_id TEXT PRIMARY KEY,
            sample_type TEXT NOT NULL,
            operator TEXT NOT NULL,
            collection_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Registered'
        )
    ''')

    # Table 2: reference_samples (Known/Reference samples)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reference_samples (
            reference_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            subject_label TEXT NOT NULL,
            operator TEXT NOT NULL,
            collection_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Registered'
        )
    ''')

    # Table 3: pcr_runs (Thermal telemetry for Evidence or Reference samples)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pcr_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_ref_id TEXT NOT NULL,
            sample_ref_type TEXT NOT NULL DEFAULT 'Evidence',
            timestamp TEXT NOT NULL,
            temperature REAL NOT NULL,
            cycle_number INTEGER NOT NULL,
            progress_percent REAL NOT NULL,
            run_status TEXT NOT NULL
        )
    ''')

    # Table 4: str_profiling_runs (5-stage pipeline step tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS str_profiling_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_ref_id TEXT NOT NULL,
            sample_ref_type TEXT NOT NULL DEFAULT 'Evidence',
            stage TEXT NOT NULL,
            stage_status TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    # Table 5: profiles (5-locus STR synthetic profiles)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            sample_ref_id TEXT PRIMARY KEY,
            sample_ref_type TEXT NOT NULL DEFAULT 'Evidence',
            locus_1 TEXT NOT NULL,
            locus_2 TEXT NOT NULL,
            locus_3 TEXT NOT NULL,
            locus_4 TEXT NOT NULL,
            locus_5 TEXT NOT NULL,
            generated_at TEXT NOT NULL
        )
    ''')

    # Table 6: custody_blocks (SHA-256 hash-chain ledger)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custody_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_index INTEGER NOT NULL UNIQUE,
            sample_ref_id TEXT NOT NULL,
            sample_ref_type TEXT NOT NULL DEFAULT 'Evidence',
            event_name TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            data_hash TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            block_hash TEXT NOT NULL
        )
    ''')

    # Table 7: comparisons (DNA profile comparison records)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id TEXT NOT NULL,
            reference_id_or_evidence_id_2 TEXT NOT NULL,
            result TEXT NOT NULL,
            compared_at TEXT NOT NULL
        )
    ''')

    conn.commit()

    # Check if database needs demo seed data
    cursor.execute('SELECT COUNT(*) FROM samples')
    sample_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM reference_samples')
    ref_count = cursor.fetchone()[0]

    conn.close()

    if sample_count == 0 and ref_count == 0:
        seed_demo_data()

def seed_demo_data():
    """Populates realistic seed demo data for Evidence & Reference samples."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Evidence Sample E001 (Profiled)
    cursor.execute('''
        INSERT INTO samples (evidence_id, sample_type, operator, collection_time, status)
        VALUES ('E001', 'Blood', 'OP-402 (Dr. Vance)', '2026-09-10 09:15:00', 'Profile Generated')
    ''')
    
    # 2. Reference Sample R001 (Suspect A - Profiled matching E001)
    cursor.execute('''
        INSERT INTO reference_samples (reference_id, source_type, subject_label, operator, collection_time, status)
        VALUES ('R001', 'Suspect', 'Suspect Alpha', 'OP-109 (Tech. Chen)', '2026-09-10 11:30:00', 'Profile Generated')
    ''')

    # 3. Evidence Sample E002 (PCR Complete ready for STR profiling)
    cursor.execute('''
        INSERT INTO samples (evidence_id, sample_type, operator, collection_time, status)
        VALUES ('E002', 'Saliva', 'OP-402 (Dr. Vance)', '2026-09-11 14:00:00', 'PCR Complete')
    ''')

    # 4. Reference Sample R002 (Victim B - Registered)
    cursor.execute('''
        INSERT INTO reference_samples (reference_id, source_type, subject_label, operator, collection_time, status)
        VALUES ('R002', 'Victim', 'Victim Beta', 'OP-109 (Tech. Chen)', '2026-09-12 10:20:00', 'Registered')
    ''')

    # Synthetic Profile for E001 (Matching R001)
    cursor.execute('''
        INSERT INTO profiles (sample_ref_id, sample_ref_type, locus_1, locus_2, locus_3, locus_4, locus_5, generated_at)
        VALUES ('E001', 'Evidence', '7, 9.3', '14, 17', '8, 11', '10, 12', '11, 13', '2026-09-10 10:50:00')
    ''')

    # Synthetic Profile for R001 (Matching E001)
    cursor.execute('''
        INSERT INTO profiles (sample_ref_id, sample_ref_type, locus_1, locus_2, locus_3, locus_4, locus_5, generated_at)
        VALUES ('R001', 'Reference', '7, 9.3', '14, 17', '8, 11', '10, 12', '11, 13', '2026-09-10 13:00:00')
    ''')

    conn.commit()
    conn.close()

    # Log Blockchain Custody Blocks for E001
    blockchain.add_custody_block('E001', 'Evidence', 'Collected', '2026-09-10 09:15:00')
    blockchain.add_custody_block('E001', 'Evidence', 'Received by device', '2026-09-10 10:00:00')
    blockchain.add_custody_block('E001', 'Evidence', 'PCR started', '2026-09-10 10:05:00')
    blockchain.add_custody_block('E001', 'Evidence', 'PCR completed', '2026-09-10 10:45:00')
    blockchain.add_custody_block('E001', 'Evidence', 'Analysis completed', '2026-09-10 10:48:00')
    blockchain.add_custody_block('E001', 'Evidence', 'Result stored', '2026-09-10 10:50:00')

    # Log Blockchain Custody Blocks for R001
    blockchain.add_custody_block('R001', 'Reference', 'Collected', '2026-09-10 11:30:00')
    blockchain.add_custody_block('R001', 'Reference', 'Received by device', '2026-09-10 12:10:00')
    blockchain.add_custody_block('R001', 'Reference', 'PCR started', '2026-09-10 12:15:00')
    blockchain.add_custody_block('R001', 'Reference', 'PCR completed', '2026-09-10 12:55:00')
    blockchain.add_custody_block('R001', 'Reference', 'Analysis completed', '2026-09-10 12:58:00')
    blockchain.add_custody_block('R001', 'Reference', 'Result stored', '2026-09-10 13:00:00')

    # Log Custody Blocks for E002 and R002
    blockchain.add_custody_block('E002', 'Evidence', 'Collected', '2026-09-11 14:00:00')
    blockchain.add_custody_block('E002', 'Evidence', 'Received by device', '2026-09-11 14:30:00')
    blockchain.add_custody_block('E002', 'Evidence', 'PCR started', '2026-09-11 14:35:00')
    blockchain.add_custody_block('E002', 'Evidence', 'PCR completed', '2026-09-11 15:15:00')

    blockchain.add_custody_block('R002', 'Reference', 'Collected', '2026-09-12 10:20:00')


# --- Helper Functions for ID Generation & Samples ---

def generate_next_evidence_id():
    """Auto-generates sequential Evidence IDs (e.g. E001, E002, E003...)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT evidence_id FROM samples ORDER BY rowid DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row and row['evidence_id'].startswith('E') and row['evidence_id'][1:].isdigit():
        num = int(row['evidence_id'][1:]) + 1
        return f"E{num:03d}"
    return "E001"

def generate_next_reference_id():
    """Auto-generates sequential Reference IDs (e.g. R001, R002, R003...)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT reference_id FROM reference_samples ORDER BY rowid DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row and row['reference_id'].startswith('R') and row['reference_id'][1:].isdigit():
        num = int(row['reference_id'][1:]) + 1
        return f"R{num:03d}"
    return "R001"

def add_sample(evidence_id, sample_type, operator, collection_time):
    """
    Registers a new evidence sample in SQLite table 'samples'.
    Appends a 'Collected' custody block to the blockchain ledger.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not collection_time:
        collection_time = now_str

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO samples (evidence_id, sample_type, operator, collection_time, status)
        VALUES (?, ?, ?, ?, 'Registered')
    ''', (evidence_id, sample_type, operator, collection_time))
    conn.commit()
    conn.close()

    blockchain.add_custody_block(evidence_id, 'Evidence', 'Collected', collection_time)

def add_reference_sample(reference_id, source_type, subject_label, operator, collection_time):
    """
    Registers a new reference sample in SQLite table 'reference_samples'.
    Appends a 'Collected' custody block to the blockchain ledger (tagged sample_ref_type='Reference').
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not collection_time:
        collection_time = now_str

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reference_samples (reference_id, source_type, subject_label, operator, collection_time, status)
        VALUES (?, ?, ?, ?, ?, 'Registered')
    ''', (reference_id, source_type, subject_label, operator, collection_time))
    conn.commit()
    conn.close()

    blockchain.add_custody_block(reference_id, 'Reference', 'Collected', collection_time)

def get_all_samples():
    """Retrieves all evidence samples."""
    conn = get_db_connection()
    samples = conn.execute('SELECT * FROM samples ORDER BY rowid DESC').fetchall()
    conn.close()
    return [dict(s) for s in samples]

def get_all_reference_samples():
    """Retrieves all reference samples."""
    conn = get_db_connection()
    refs = conn.execute('SELECT * FROM reference_samples ORDER BY rowid DESC').fetchall()
    conn.close()
    return [dict(r) for r in refs]

def get_sample(evidence_id):
    """Retrieves a single evidence sample."""
    conn = get_db_connection()
    sample = conn.execute('SELECT * FROM samples WHERE evidence_id = ?', (evidence_id,)).fetchone()
    conn.close()
    return dict(sample) if sample else None

def get_reference_sample(reference_id):
    """Retrieves a single reference sample."""
    conn = get_db_connection()
    ref = conn.execute('SELECT * FROM reference_samples WHERE reference_id = ?', (reference_id,)).fetchone()
    conn.close()
    return dict(ref) if ref else None

def get_sample_or_reference(sample_ref_id):
    """
    Lookup helper that checks evidence samples first, then reference samples.
    Returns dict with attached 'sample_ref_type' ('Evidence' or 'Reference').
    """
    s = get_sample(sample_ref_id)
    if s:
        s['sample_ref_type'] = 'Evidence'
        s['display_label'] = f"{s['evidence_id']} (Evidence - {s['sample_type']})"
        return s
    
    r = get_reference_sample(sample_ref_id)
    if r:
        r['sample_ref_type'] = 'Reference'
        r['evidence_id'] = r['reference_id']
        r['sample_type'] = f"{r['source_type']} ({r['subject_label']})"
        r['display_label'] = f"{r['reference_id']} (Reference - {r['subject_label']})"
        return r
    
    return None

def update_sample_status(sample_ref_id, sample_ref_type, status):
    """Updates status for evidence sample OR reference sample."""
    conn = get_db_connection()
    if sample_ref_type == 'Reference':
        conn.execute('UPDATE reference_samples SET status = ? WHERE reference_id = ?', (status, sample_ref_id))
    else:
        conn.execute('UPDATE samples SET status = ? WHERE evidence_id = ?', (status, sample_ref_id))
    conn.commit()
    conn.close()

# --- Hardware PCR Telemetry Operations ---

def add_pcr_telemetry(sample_ref_id, sample_ref_type, temperature, cycle_number, progress_percent, run_status):
    """Records real-time PCR hardware telemetry into pcr_runs table."""
    conn = get_db_connection()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute('''
        INSERT INTO pcr_runs (sample_ref_id, sample_ref_type, timestamp, temperature, cycle_number, progress_percent, run_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (sample_ref_id, sample_ref_type, ts, temperature, cycle_number, progress_percent, run_status))
    conn.commit()
    conn.close()

def get_pcr_telemetry(sample_ref_id):
    """Retrieves all PCR telemetry points for a sample."""
    conn = get_db_connection()
    runs = conn.execute('''
        SELECT * FROM pcr_runs 
        WHERE sample_ref_id = ? 
        ORDER BY id ASC
    ''', (sample_ref_id,)).fetchall()
    conn.close()
    return [dict(r) for r in runs]

def get_latest_pcr_run(sample_ref_id):
    """Retrieves the latest PCR telemetry point for a sample."""
    conn = get_db_connection()
    run = conn.execute('''
        SELECT * FROM pcr_runs 
        WHERE sample_ref_id = ? 
        ORDER BY id DESC LIMIT 1
    ''', (sample_ref_id,)).fetchone()
    conn.close()
    return dict(run) if run else None

# --- Profiles & Comparison Operations ---

def get_profile(sample_ref_id):
    """Retrieves profile for a given evidence or reference sample ID."""
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM profiles WHERE sample_ref_id = ?', (sample_ref_id,)).fetchone()
    conn.close()
    return dict(profile) if profile else None

def get_all_profiles():
    """Retrieves all stored profiles with metadata labels."""
    conn = get_db_connection()
    profiles = conn.execute('SELECT * FROM profiles ORDER BY generated_at DESC').fetchall()
    conn.close()

    result = []
    for p in profiles:
        p_dict = dict(p)
        info = get_sample_or_reference(p_dict['sample_ref_id'])
        if info:
            p_dict['operator'] = info.get('operator', 'Unknown')
            p_dict['sample_type'] = info.get('sample_type', 'Unknown')
            p_dict['display_label'] = info.get('display_label', p_dict['sample_ref_id'])
        else:
            p_dict['operator'] = 'Unknown'
            p_dict['sample_type'] = 'Unknown'
            p_dict['display_label'] = p_dict['sample_ref_id']
        result.append(p_dict)
    return result

def compare_profiles(sample_id_1, sample_id_2):
    """
    Performs locus-by-locus STR profile comparison between two samples (Evidence or Reference).
    Saves result to comparisons table and logs 'Compared' custody block to blockchain.
    Returns comparison breakdown dictionary.
    """
    prof1 = get_profile(sample_id_1)
    prof2 = get_profile(sample_id_2)

    s1_info = get_sample_or_reference(sample_id_1)
    s2_info = get_sample_or_reference(sample_id_2)

    if not prof1 or not prof2:
        return {
            'overall': 'INCONCLUSIVE',
            'reason': 'One or both DNA profiles are missing from the database.',
            'loci': [],
            'sample_1': s1_info,
            'sample_2': s2_info
        }

    loci_mapping = [
        ('TH01', 'locus_1'),
        ('vWA', 'locus_2'),
        ('TPOX', 'locus_3'),
        ('CSF1PO', 'locus_4'),
        ('D16S539', 'locus_5')
    ]

    loci_results = []
    match_count = 0

    for display_name, col in loci_mapping:
        val1 = prof1[col]
        val2 = prof2[col]
        is_match = (val1 == val2)
        if is_match:
            match_count += 1
        loci_results.append({
            'locus': display_name,
            'allele_1': val1,
            'allele_2': val2,
            'match': is_match
        })

    if match_count == len(loci_mapping):
        overall = 'CONSISTENT'
    else:
        overall = 'DIFFERENT'

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update sample statuses to 'Compared'
    if s1_info:
        update_sample_status(sample_id_1, s1_info['sample_ref_type'], 'Compared')
    if s2_info:
        update_sample_status(sample_id_2, s2_info['sample_ref_type'], 'Compared')

    # Record comparison in comparisons table
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO comparisons (evidence_id, reference_id_or_evidence_id_2, result, compared_at)
        VALUES (?, ?, ?, ?)
    ''', (sample_id_1, sample_id_2, overall, now_str))
    conn.commit()
    conn.close()

    # Log 'Compared' block to custody blockchain for BOTH samples
    if s1_info:
        blockchain.add_custody_block(
            sample_id_1, 
            s1_info['sample_ref_type'], 
            f"Compared with {sample_id_2} (Result: {overall})", 
            now_str
        )
    if s2_info:
        blockchain.add_custody_block(
            sample_id_2, 
            s2_info['sample_ref_type'], 
            f"Compared with {sample_id_1} (Result: {overall})", 
            now_str
        )

    return {
        'overall': overall,
        'match_count': match_count,
        'total_loci': len(loci_mapping),
        'loci': loci_results,
        'sample_1': s1_info,
        'sample_2': s2_info,
        'compared_at': now_str
    }

def get_comparisons_for_sample(sample_ref_id):
    """Retrieves all past profile comparisons involving a specific sample ID."""
    conn = get_db_connection()
    comps = conn.execute('''
        SELECT * FROM comparisons 
        WHERE evidence_id = ? OR reference_id_or_evidence_id_2 = ?
        ORDER BY id DESC
    ''', (sample_ref_id, sample_ref_id)).fetchall()
    conn.close()
    return [dict(c) for c in comps]
