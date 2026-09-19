"""
NucleoX - On-Spot DNA Analysis System (Flask Web Application)
Main application module routing all 8 core functional modules:
1. Dashboard Homepage
2. Evidence Sample Registration
3. Reference Sample Registration
4. Device PCR Thermal Telemetry Monitoring
5. 5-Stage STR Profiling Simulation & Electropherogram Visualization
6. Digital Blockchain-Backed Chain of Custody Ledger & Tamper Verification
7. STR Profile Locus Comparison (Evidence vs Reference or Evidence vs Evidence)
8. Printable Summary Forensic Report Generation
"""

import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import database
import str_profiling
import blockchain
from hardware import hardware_manager

app = Flask(__name__)
app.secret_key = "nucleox_secret_hackathon_key_2026"

# Initialize SQLite database schema and seed demo data on startup
database.init_db()


# ==============================================================================
# ROUTE 1: DASHBOARD / HOME PAGE (Module 7)
# NucleoX header branding, overview metrics, evidence samples table, and reference samples table.
# ==============================================================================
@app.route('/')
def index():
    """
    Dashboard homepage listing evidence and reference samples, metrics, and navigation shortcuts.
    Displays splash screen overlay on first load.
    """
    evidence_samples = database.get_all_samples()
    reference_samples = database.get_all_reference_samples()

    total_evidence = len(evidence_samples)
    total_reference = len(reference_samples)
    
    all_samples = evidence_samples + reference_samples
    pcr_running = sum(1 for s in all_samples if s['status'] == 'PCR Running')
    pcr_complete = sum(1 for s in all_samples if s['status'] in ['PCR Complete', 'Profile Generated', 'Compared'])
    profiles_count = sum(1 for s in all_samples if s['status'] in ['Profile Generated', 'Compared'])

    return render_template(
        'index.html',
        evidence_samples=evidence_samples,
        reference_samples=reference_samples,
        total_evidence=total_evidence,
        total_reference=total_reference,
        pcr_running=pcr_running,
        pcr_complete=pcr_complete,
        profiles_count=profiles_count
    )


# ==============================================================================
# ROUTE 2: EVIDENCE REGISTRATION (Module 1)
# Register crime scene DNA evidence samples (E001, E002...)
# ==============================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles evidence sample registration.
    - GET: Form with auto-generated ID (E001...) and evidence samples table.
    - POST: Inserts into 'samples' and logs 'Collected' custody block to blockchain ledger.
    """
    if request.method == 'POST':
        evidence_id = request.form.get('evidence_id')
        sample_type = request.form.get('sample_type')
        operator = request.form.get('operator')
        collection_time = request.form.get('collection_time')

        if not evidence_id:
            evidence_id = database.generate_next_evidence_id()

        database.add_sample(evidence_id, sample_type, operator, collection_time)
        flash(f"Evidence Sample {evidence_id} registered successfully!", "success")
        return redirect(url_for('register'))

    next_id = database.generate_next_evidence_id()
    samples = database.get_all_samples()
    return render_template('register.html', next_id=next_id, samples=samples)


# ==============================================================================
# ROUTE 3: REFERENCE SAMPLE REGISTRATION (Module 2)
# Register known reference samples (Suspect, Victim, Elimination, Known) (R001, R002...)
# ==============================================================================
@app.route('/register_reference', methods=['GET', 'POST'])
def register_reference():
    """
    Handles reference sample registration.
    - GET: Form with auto-generated ID (R001...) and reference samples table.
    - POST: Inserts into 'reference_samples' and logs 'Collected' custody block to blockchain.
    """
    if request.method == 'POST':
        reference_id = request.form.get('reference_id')
        source_type = request.form.get('source_type')
        subject_label = request.form.get('subject_label')
        operator = request.form.get('operator')
        collection_time = request.form.get('collection_time')

        if not reference_id:
            reference_id = database.generate_next_reference_id()

        database.add_reference_sample(reference_id, source_type, subject_label, operator, collection_time)
        flash(f"Reference Sample {reference_id} ({subject_label}) registered successfully!", "success")
        return redirect(url_for('register_reference'))

    next_id = database.generate_next_reference_id()
    reference_samples = database.get_all_reference_samples()
    return render_template('register_reference.html', next_id=next_id, reference_samples=reference_samples)


# ==============================================================================
# ROUTE 4: DEVICE MONITORING (Module 3)
# Ingestion of ESP32 USB serial thermal telemetry or simulator execution.
# ==============================================================================
@app.route('/device')
def device():
    """
    Renders hardware execution and thermal telemetry interface.
    Supports both Evidence and Reference samples for PCR thermal cycling.
    """
    selected_id = request.args.get('sample_ref_id', '') or request.args.get('evidence_id', '')
    
    evidence_samples = database.get_all_samples()
    reference_samples = database.get_all_reference_samples()
    
    # Merge and annotate sample choices for selector dropdown
    all_eligible = []
    for s in evidence_samples:
        all_eligible.append({
            'id': s['evidence_id'],
            'type': 'Evidence',
            'label': f"{s['evidence_id']} (Evidence - {s['sample_type']})",
            'status': s['status']
        })
    for r in reference_samples:
        all_eligible.append({
            'id': r['reference_id'],
            'type': 'Reference',
            'label': f"{r['reference_id']} (Reference - {r['subject_label']})",
            'status': r['status']
        })

    available_ports = hardware_manager.get_available_ports()
    
    telemetry = []
    selected_sample = None
    if selected_id:
        telemetry = database.get_pcr_telemetry(selected_id)
        selected_sample = database.get_sample_or_reference(selected_id)

    return render_template(
        'device.html',
        samples=all_eligible,
        selected_id=selected_id,
        selected_sample=selected_sample,
        available_ports=available_ports,
        telemetry=telemetry
    )

@app.route('/api/start_pcr', methods=['POST'])
def api_start_pcr():
    """API endpoint to trigger PCR thermal run for Evidence or Reference sample."""
    data = request.get_json() or {}
    sample_ref_id = data.get('sample_ref_id') or data.get('evidence_id')
    port = data.get('port')

    if not sample_ref_id:
        return jsonify({'success': False, 'message': 'Sample ID is required.'}), 400

    info = database.get_sample_or_reference(sample_ref_id)
    if not info:
        return jsonify({'success': False, 'message': 'Sample not found.'}), 404

    sample_ref_type = info['sample_ref_type']

    if port and port != 'COM3 (Simulated)':
        hardware_manager.connect_serial(port)

    success, msg = hardware_manager.start_pcr_run(sample_ref_id, sample_ref_type)
    return jsonify({'success': success, 'message': msg})

@app.route('/api/pcr_data/<sample_ref_id>')
def api_pcr_data(sample_ref_id):
    """API endpoint returning live PCR telemetry JSON for dynamic chart updates."""
    sample = database.get_sample_or_reference(sample_ref_id)
    telemetry = database.get_pcr_telemetry(sample_ref_id)
    latest = telemetry[-1] if telemetry else None

    return jsonify({
        'sample': sample,
        'telemetry': telemetry,
        'latest': latest
    })


# ==============================================================================
# ROUTE 5: STR PROFILING SIMULATION (Module 4)
# Stepped 5-stage STR pipeline execution, electropherogram peak visualizer, 5 loci allele table.
# ==============================================================================
@app.route('/profiles')
def profiles():
    """
    Renders STR Profiling Simulation interface.
    Displays electropherogram peak charts and 5-locus STR profile table with disclaimer.
    """
    selected_id = request.args.get('sample_ref_id', '') or request.args.get('evidence_id', '')
    
    evidence_samples = database.get_all_samples()
    reference_samples = database.get_all_reference_samples()
    
    eligible = []
    for s in evidence_samples:
        if s['status'] in ['PCR Complete', 'Profile Generated', 'Compared']:
            eligible.append({
                'id': s['evidence_id'],
                'type': 'Evidence',
                'label': f"{s['evidence_id']} (Evidence - {s['sample_type']})",
                'status': s['status']
            })
    for r in reference_samples:
        if r['status'] in ['PCR Complete', 'Profile Generated', 'Compared']:
            eligible.append({
                'id': r['reference_id'],
                'type': 'Reference',
                'label': f"{r['reference_id']} (Reference - {r['subject_label']})",
                'status': r['status']
            })

    profile = None
    peaks = None
    pipeline_runs = []
    selected_sample = None

    if selected_id:
        selected_sample = database.get_sample_or_reference(selected_id)
        profile = database.get_profile(selected_id)
        pipeline_runs = str_profiling.get_str_pipeline_runs(selected_id)
        if profile:
            peaks, _ = str_profiling.generate_deterministic_peaks(selected_id)

    all_profiles = database.get_all_profiles()

    return render_template(
        'profiles.html',
        samples=eligible,
        selected_id=selected_id,
        selected_sample=selected_sample,
        profile=profile,
        peaks=peaks,
        pipeline_runs=pipeline_runs,
        all_profiles=all_profiles
    )

@app.route('/api/run_str_pipeline/<sample_ref_id>', methods=['POST'])
def api_run_str_pipeline(sample_ref_id):
    """API endpoint to execute 5-stage STR profiling pipeline simulation."""
    info = database.get_sample_or_reference(sample_ref_id)
    if not info:
        return jsonify({'success': False, 'message': 'Sample not found.'}), 404

    alleles = str_profiling.execute_str_pipeline(sample_ref_id, info['sample_ref_type'])
    return jsonify({
        'success': True, 
        'message': f'5-Stage STR profiling completed for {sample_ref_id}.',
        'alleles': alleles
    })


# ==============================================================================
# ROUTE 6: BLOCKCHAIN CHAIN OF CUSTODY (Module 5)
# Vertical timeline of SHA-256 hash blocks & interactive chain integrity verifier.
# ==============================================================================
@app.route('/custody')
def custody():
    """
    Renders Digital Chain of Custody ledger.
    Shows SHA-256 hash-chain blocks with verification controls and disclaimer.
    """
    selected_id = request.args.get('sample_ref_id', '') or request.args.get('evidence_id', '')
    
    evidence_samples = database.get_all_samples()
    reference_samples = database.get_all_reference_samples()
    all_samples = [
        {'id': s['evidence_id'], 'label': f"{s['evidence_id']} (Evidence)"} for s in evidence_samples
    ] + [
        {'id': r['reference_id'], 'label': f"{r['reference_id']} (Reference - {r['subject_label']})"} for r in reference_samples
    ]

    blocks = blockchain.get_custody_chain(selected_id if selected_id else None)
    verification = blockchain.verify_chain_integrity()

    return render_template(
        'custody.html',
        samples=all_samples,
        selected_id=selected_id,
        blocks=blocks,
        verification=verification
    )

@app.route('/api/verify_chain')
def api_verify_chain():
    """API endpoint to perform live SHA-256 hash chain integrity re-calculation."""
    res = blockchain.verify_chain_integrity()
    return jsonify(res)


# ==============================================================================
# ROUTE 7: PROFILE COMPARISON (Module 6)
# Locus-by-locus comparison between two samples (Evidence vs Evidence or Evidence vs Reference).
# ==============================================================================
@app.route('/compare', methods=['GET', 'POST'])
def compare():
    """
    Handles DNA profile comparison matching two profiles.
    - GET: Shows selector dropdowns for all profiled samples.
    - POST: Executes locus comparison, saves result to DB, and logs custody block.
    """
    all_profiles = database.get_all_profiles()
    
    sample_1 = request.args.get('sample_1') or request.form.get('sample_1')
    sample_2 = request.args.get('sample_2') or request.form.get('sample_2')

    result = None
    if sample_1 and sample_2:
        result = database.compare_profiles(sample_1, sample_2)

    return render_template(
        'compare.html',
        profiles=all_profiles,
        sample_1=sample_1,
        sample_2=sample_2,
        result=result
    )


# ==============================================================================
# ROUTE 8: PRINTABLE REPORT GENERATION (Module 8)
# Generates comprehensive printable summary report for Evidence or Reference sample.
# ==============================================================================
@app.route('/report/<sample_ref_id>')
def report(sample_ref_id):
    """
    Renders printable forensic summary report for an Evidence or Reference sample.
    Includes PCR telemetry summary, STR pipeline execution, profile table, comparisons, and hash-chain verification.
    """
    sample = database.get_sample_or_reference(sample_ref_id)
    if not sample:
        flash(f"Sample {sample_ref_id} not found.", "danger")
        return redirect(url_for('index'))

    profile = database.get_profile(sample_ref_id)
    peaks = None
    if profile:
        peaks, _ = str_profiling.generate_deterministic_peaks(sample_ref_id)

    custody_blocks = blockchain.get_custody_chain(sample_ref_id)
    chain_verification = blockchain.verify_chain_integrity()
    latest_pcr = database.get_latest_pcr_run(sample_ref_id)
    pcr_telemetry = database.get_pcr_telemetry(sample_ref_id)
    pipeline_runs = str_profiling.get_str_pipeline_runs(sample_ref_id)
    comparisons = database.get_comparisons_for_sample(sample_ref_id)

    return render_template(
        'report.html',
        sample=sample,
        profile=profile,
        peaks=peaks,
        custody_blocks=custody_blocks,
        chain_verification=chain_verification,
        latest_pcr=latest_pcr,
        pcr_count=len(pcr_telemetry),
        pipeline_runs=pipeline_runs,
        comparisons=comparisons
    )


if __name__ == '__main__':
    print("==========================================================")
    print(" NucleoX - On-Spot DNA Analysis System")
    print(" Server running on http://127.0.0.1:5000")
    print(" Synthetic DNA Data — Prototype for Hackathon Demonstration")
    print("==========================================================")
    app.run(debug=True, host='0.0.0.0', port=5000)
