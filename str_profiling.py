"""
NucleoX - STR Profiling Module
Simulates the 5-stage Short Tandem Repeat (STR) DNA profiling pipeline:
  1. DNA Extraction (cosmetic timestamped step)
  2. PCR Amplification (summarizes telemetry from pcr_runs)
  3. Capillary Electrophoresis (generates simulated electropherogram peak charts for 5 loci)
  4. Allele Calling (deterministically converts peak positions into standard STR allele pairs)
  5. Profile Generated (saves row to profiles table & logs custody block)

All generated DNA profile data is synthetic for demonstration purposes only.
"""

import time
import random
import hashlib
from datetime import datetime
import database
import blockchain

LOCI_NAMES = ['TH01', 'vWA', 'TPOX', 'CSF1PO', 'D16S539']

# Preset allele options per locus for realistic forensic simulation
LOCI_ALLELE_POOLS = {
    'TH01': ['6, 7', '7, 9.3', '9.3, 10', '8, 9.3', '6, 9.3'],
    'vWA': ['14, 17', '15, 16', '16, 18', '14, 15', '17, 19'],
    'TPOX': ['8, 11', '8, 8', '9, 11', '8, 12', '11, 11'],
    'CSF1PO': ['10, 12', '11, 13', '10, 11', '12, 12', '9, 11'],
    'D16S539': ['11, 13', '9, 12', '11, 12', '13, 14', '10, 13']
}

def generate_deterministic_peaks(sample_ref_id):
    """
    Generates synthetic Capillary Electrophoresis peak telemetry for 5 STR loci.
    Uses MD5 seed of sample_ref_id so the electropherogram peaks and derived alleles
    are 100% deterministic and reproducible per sample.
    """
    # Seed random generator with sample_ref_id hash
    hash_seed = int(hashlib.md5(sample_ref_id.encode('utf-8')).hexdigest(), 16)
    rng = random.Random(hash_seed)

    electropherogram = {}
    profile_alleles = {}

    for locus in LOCI_NAMES:
        pool = LOCI_ALLELE_POOLS[locus]
        allele_pair_str = rng.choice(pool)
        alleles = [a.strip() for a in allele_pair_str.split(',')]
        profile_alleles[locus] = allele_pair_str

        # Generate realistic peak charts (RFU heights between 800 - 2400)
        locus_peaks = []
        base_pos = 100 + LOCI_NAMES.index(locus) * 50

        for idx, allele in enumerate(alleles):
            try:
                allele_val = float(allele)
            except ValueError:
                allele_val = 9.3

            pos = round(base_pos + (allele_val * 3.5), 1)
            height = rng.randint(900, 2300)
            locus_peaks.append({
                'allele': allele,
                'position_bp': pos,
                'rfu_height': height
            })
        
        # Add 1-2 minor noise peaks for electropherogram realism
        noise_pos = round(base_pos + rng.uniform(5, 40), 1)
        noise_height = rng.randint(120, 280)
        locus_peaks.append({
            'allele': 'Artifact',
            'position_bp': noise_pos,
            'rfu_height': noise_height
        })

        # Sort peaks by position
        locus_peaks.sort(key=lambda x: x['position_bp'])
        electropherogram[locus] = locus_peaks

    return electropherogram, profile_alleles

def execute_str_pipeline(sample_ref_id, sample_ref_type):
    """
    Executes the 5-stage STR profiling sequence:
    1. DNA Extraction
    2. PCR Amplification
    3. Capillary Electrophoresis
    4. Allele Calling
    5. Profile Generated
    Writes progress logs to str_profiling_runs and final result to profiles table.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()

    stages = [
        ("DNA Extraction", "Completed"),
        ("PCR Amplification", "Completed"),
        ("Capillary Electrophoresis", "Completed"),
        ("Allele Calling", "Completed"),
        ("Profile Generated", "Completed")
    ]

    for stage_name, status in stages:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO str_profiling_runs (sample_ref_id, sample_ref_type, stage, stage_status, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_ref_id, sample_ref_type, stage_name, status, now_str))
        conn.commit()

    # Generate profile alleles
    _, profile_alleles = generate_deterministic_peaks(sample_ref_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT OR REPLACE INTO profiles 
        (sample_ref_id, sample_ref_type, locus_1, locus_2, locus_3, locus_4, locus_5, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        sample_ref_id,
        sample_ref_type,
        profile_alleles['TH01'],
        profile_alleles['vWA'],
        profile_alleles['TPOX'],
        profile_alleles['CSF1PO'],
        profile_alleles['D16S539'],
        now_str
    ))

    # Update sample status in appropriate table
    if sample_ref_type == 'Reference':
        cursor.execute("UPDATE reference_samples SET status = 'Profile Generated' WHERE reference_id = ?", (sample_ref_id,))
    else:
        cursor.execute("UPDATE samples SET status = 'Profile Generated' WHERE evidence_id = ?", (sample_ref_id,))

    conn.commit()
    conn.close()

    # Log to hash-chain digital chain of custody
    blockchain.add_custody_block(sample_ref_id, sample_ref_type, "Result stored", now_str)

    return profile_alleles

def get_str_pipeline_runs(sample_ref_id):
    """Retrieves all STR pipeline step execution logs for a given sample."""
    conn = database.get_db_connection()
    runs = conn.execute('''
        SELECT * FROM str_profiling_runs 
        WHERE sample_ref_id = ? 
        ORDER BY id ASC
    ''', (sample_ref_id,)).fetchall()
    conn.close()
    return [dict(r) for r in runs]
