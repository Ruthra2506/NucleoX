"""
NucleoX - Blockchain Module
Provides append-only hash-linked ledger functionality for digital chain-of-custody logging.

Each event (Collected / Received by device / PCR started / PCR completed /
Analysis completed / Result stored / Compared) is recorded as a block containing:
- block_index: Sequential integer ID of the block
- sample_ref_id: Evidence or Reference sample identifier (e.g. E001, R001)
- sample_ref_type: 'Evidence' or 'Reference'
- event_name: Description of the custody event
- event_timestamp: Timestamp of the event
- data_hash: SHA-256 hash of event fields
- previous_hash: block_hash of the immediately preceding block ("0" for genesis block)
- block_hash: SHA-256 hash of (data_hash + previous_hash)

Includes chain integrity verification to recompute and validate block hashes.
"""

import hashlib
from datetime import datetime
import database

def calculate_data_hash(block_index, sample_ref_id, sample_ref_type, event_name, event_timestamp):
    """
    Computes SHA-256 hash of block's intrinsic event data payload.
    """
    payload = f"{block_index}|{sample_ref_id}|{sample_ref_type}|{event_name}|{event_timestamp}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def calculate_block_hash(data_hash, previous_hash):
    """
    Computes SHA-256 hash of data_hash combined with the previous block's hash.
    """
    payload = f"{data_hash}|{previous_hash}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def add_custody_block(sample_ref_id, sample_ref_type, event_name, event_timestamp=None):
    """
    Creates and appends a new block to the custody_blocks table in SQLite database.
    Links to the block_hash of the previous block in the ledger.
    """
    if not event_timestamp:
        event_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Determine next block_index and previous_hash
    cursor.execute("SELECT block_index, block_hash FROM custody_blocks ORDER BY block_index DESC LIMIT 1")
    last_block = cursor.fetchone()

    if last_block:
        block_index = last_block['block_index'] + 1
        previous_hash = last_block['block_hash']
    else:
        block_index = 1
        previous_hash = "0"  # Genesis block previous hash

    # Compute hashes
    data_hash = calculate_data_hash(block_index, sample_ref_id, sample_ref_type, event_name, event_timestamp)
    block_hash = calculate_block_hash(data_hash, previous_hash)

    # Insert block into custody_blocks ledger
    cursor.execute('''
        INSERT INTO custody_blocks 
        (block_index, sample_ref_id, sample_ref_type, event_name, event_timestamp, data_hash, previous_hash, block_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (block_index, sample_ref_id, sample_ref_type, event_name, event_timestamp, data_hash, previous_hash, block_hash))

    conn.commit()
    conn.close()

    return {
        'block_index': block_index,
        'sample_ref_id': sample_ref_id,
        'sample_ref_type': sample_ref_type,
        'event_name': event_name,
        'event_timestamp': event_timestamp,
        'data_hash': data_hash,
        'previous_hash': previous_hash,
        'block_hash': block_hash
    }

def get_custody_chain(sample_ref_id=None):
    """
    Retrieves custody blocks ordered chronologically by block_index.
    If sample_ref_id is provided, filters for that specific sample.
    """
    conn = database.get_db_connection()
    if sample_ref_id:
        blocks = conn.execute('''
            SELECT * FROM custody_blocks 
            WHERE sample_ref_id = ? 
            ORDER BY block_index ASC
        ''', (sample_ref_id,)).fetchall()
    else:
        blocks = conn.execute('''
            SELECT * FROM custody_blocks 
            ORDER BY block_index ASC
        ''').fetchall()
    conn.close()
    return [dict(b) for b in blocks]

def verify_chain_integrity():
    """
    Recomputes every block's data_hash and block_hash sequentially from block_index 1
    to verify that the hash-chain is unbroken and untampered.
    Returns dict with integrity status, total blocks checked, and details of any tampering.
    """
    conn = database.get_db_connection()
    blocks = conn.execute('SELECT * FROM custody_blocks ORDER BY block_index ASC').fetchall()
    conn.close()

    if not blocks:
        return {
            'is_valid': True,
            'total_blocks': 0,
            'message': 'Custody ledger is empty. No blocks to verify.'
        }

    expected_previous_hash = "0"
    for block in blocks:
        b_dict = dict(block)
        b_idx = b_dict['block_index']
        sample_ref_id = b_dict['sample_ref_id']
        sample_ref_type = b_dict['sample_ref_type']
        event_name = b_dict['event_name']
        event_timestamp = b_dict['event_timestamp']
        stored_data_hash = b_dict['data_hash']
        stored_prev_hash = b_dict['previous_hash']
        stored_block_hash = b_dict['block_hash']

        # 1. Verify previous_hash link
        if stored_prev_hash != expected_previous_hash:
            return {
                'is_valid': False,
                'total_blocks': len(blocks),
                'tampered_block_index': b_idx,
                'message': f"Hash chain broken at Block #{b_idx} ({sample_ref_id}): Stored previous_hash mismatch."
            }

        # 2. Recompute data_hash
        recomputed_data_hash = calculate_data_hash(b_idx, sample_ref_id, sample_ref_type, event_name, event_timestamp)
        if recomputed_data_hash != stored_data_hash:
            return {
                'is_valid': False,
                'total_blocks': len(blocks),
                'tampered_block_index': b_idx,
                'message': f"Data corruption detected at Block #{b_idx} ({sample_ref_id}): Event payload hash modified."
            }

        # 3. Recompute block_hash
        recomputed_block_hash = calculate_block_hash(recomputed_data_hash, stored_prev_hash)
        if recomputed_block_hash != stored_block_hash:
            return {
                'is_valid': False,
                'total_blocks': len(blocks),
                'tampered_block_index': b_idx,
                'message': f"Hash mismatch at Block #{b_idx} ({sample_ref_id}): Recomputed block hash does not match stored hash."
            }

        # Update expected previous_hash for next block iteration
        expected_previous_hash = stored_block_hash

    return {
        'is_valid': True,
        'total_blocks': len(blocks),
        'message': f"Chain integrity verified! All {len(blocks)} custody blocks are cryptographically valid."
    }
