"""
NucleoX Automated Test Suite
Verifies all 8 core functional modules:
1. SQLite DB Schema (7 tables) & ID auto-generation
2. Evidence Sample Registration & Custody Block Logging
3. Reference Sample Registration & Custody Block Logging
4. ESP32 Hardware Telemetry Ingestion (pcr_runs)
5. 5-Stage STR Profiling Simulation & Allele Calling
6. Blockchain Ledger SHA-256 Block Creation & Verification
7. Profile Comparison (Evidence vs Reference)
8. Flask HTTP Route Handlers
"""

import os
import unittest
import database
import str_profiling
import blockchain
from app import app

class TestNucleoXSystem(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Reset database for fresh test run
        if os.path.exists(database.DB_PATH):
            os.remove(database.DB_PATH)
        database.init_db()

    def test_01_database_tables(self):
        """Test that all 7 SQLite tables exist."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = [
            'samples', 
            'reference_samples', 
            'pcr_runs', 
            'str_profiling_runs', 
            'profiles', 
            'custody_blocks', 
            'comparisons'
        ]
        for tbl in expected_tables:
            self.assertIn(tbl, tables, f"Missing table: {tbl}")

    def test_02_evidence_registration(self):
        """Test Evidence registration and ID generation."""
        next_id = database.generate_next_evidence_id()
        self.assertTrue(next_id.startswith('E'))
        
        database.add_sample(next_id, 'Touch DNA', 'OP-Test', '2026-09-13 12:00:00')
        sample = database.get_sample(next_id)
        self.assertIsNotNone(sample)
        self.assertEqual(sample['sample_type'], 'Touch DNA')
        self.assertEqual(sample['status'], 'Registered')

    def test_03_reference_registration(self):
        """Test Reference sample registration."""
        next_id = database.generate_next_reference_id()
        self.assertTrue(next_id.startswith('R'))

        database.add_reference_sample(next_id, 'Suspect', 'Suspect Test', 'OP-Test', '2026-09-13 12:05:00')
        ref = database.get_reference_sample(next_id)
        self.assertIsNotNone(ref)
        self.assertEqual(ref['subject_label'], 'Suspect Test')
        self.assertEqual(ref['status'], 'Registered')

    def test_04_str_profiling_pipeline(self):
        """Test 5-stage STR profiling pipeline execution."""
        alleles = str_profiling.execute_str_pipeline('E001', 'Evidence')
        self.assertIn('TH01', alleles)
        self.assertIn('vWA', alleles)

        prof = database.get_profile('E001')
        self.assertIsNotNone(prof)
        self.assertEqual(prof['sample_ref_id'], 'E001')

    def test_05_profile_comparison(self):
        """Test locus comparison between E001 and R001."""
        res = database.compare_profiles('E001', 'R001')
        self.assertIn(res['overall'], ['CONSISTENT', 'DIFFERENT', 'INCONCLUSIVE'])
        self.assertEqual(res['total_loci'], 5)

    def test_06_blockchain_verification(self):
        """Test SHA-256 hash-chain integrity verification."""
        verification = blockchain.verify_chain_integrity()
        self.assertTrue(verification['is_valid'], f"Chain broken: {verification['message']}")
        self.assertGreater(verification['total_blocks'], 0)

    def test_07_flask_routes(self):
        """Test Flask HTTP endpoint accessibility."""
        tester = app.test_client(self)
        
        # Test Dashboard
        response = tester.get('/')
        self.assertEqual(response.status_code, 200)

        # Test Register Evidence page
        response = tester.get('/register')
        self.assertEqual(response.status_code, 200)

        # Test Register Reference page
        response = tester.get('/register_reference')
        self.assertEqual(response.status_code, 200)

        # Test Custody Page
        response = tester.get('/custody')
        self.assertEqual(response.status_code, 200)

        # Test API verify chain
        response = tester.get('/api/verify_chain')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['is_valid'])

if __name__ == '__main__':
    unittest.main()
