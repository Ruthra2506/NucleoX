"""
NucleoX - Hardware Communication Manager
Receives real-time PCR telemetry from ESP32 over USB serial connection, or
runs a non-blocking background thread thermal simulator for hackathon demo.

Emits telemetry to pcr_runs SQLite table and appends custody blocks to the
blockchain ledger when PCR runs begin and complete.
"""

import time
import threading
import json
from datetime import datetime
import database
import blockchain

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

class HardwareManager:
    """
    Manages USB serial telemetry ingestion from ESP32 hardware prototype,
    and provides a non-blocking 30-cycle PCR hardware simulator.
    """
    def __init__(self, port="COM3", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_listening = False
        self.listener_thread = None
        self.active_simulations = {}
        self.simulation_lock = threading.Lock()

    def get_available_ports(self):
        """Discovers active system COM / TTY serial ports."""
        ports = []
        if SERIAL_AVAILABLE:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                ports.append(p.device)
        if not ports:
            ports = ["COM3 (Simulated)", "COM4", "/dev/ttyUSB0", "/dev/ttyACM0"]
        return ports

    def connect_serial(self, port_name=None):
        """Attempts to open serial connection to physical ESP32 device."""
        if port_name:
            self.port = port_name
        
        if not SERIAL_AVAILABLE:
            return False, "pyserial library not installed. Running in Hardware Simulation Mode."

        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_listening = True
            self.listener_thread = threading.Thread(target=self._read_serial_loop, daemon=True)
            self.listener_thread.start()
            return True, f"Connected to ESP32 on port {self.port}"
        except Exception as e:
            return False, f"Could not connect to {self.port}: {str(e)}. Fallback to Simulator."

    def _read_serial_loop(self):
        """Background thread loop parsing incoming ESP32 serial data lines."""
        while self.is_listening and self.serial_conn and self.serial_conn.is_open:
            try:
                line = self.serial_conn.readline().decode('utf-8').strip()
                if line:
                    self._parse_and_store(line)
            except Exception as e:
                print(f"[Hardware Warning] Serial read error: {e}")
                time.sleep(1)

    def _parse_and_store(self, line):
        """
        Parses serial telemetry line from ESP32.
        Accepts JSON format: {"sample_ref_id":"E001", "type":"Evidence", "temp":95.2, "cycle":12, "progress":40.0, "status":"Running"}
        or CSV format: E001,Evidence,95.2,12,40.0,Running
        """
        try:
            sample_ref_id = None
            sample_ref_type = 'Evidence'
            temp, cycle, prog, status = 0.0, 0, 0.0, 'Running'

            if line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                sample_ref_id = data.get("sample_ref_id") or data.get("evidence_id")
                sample_ref_type = data.get("type", "Evidence")
                temp = float(data.get("temp", 0.0))
                cycle = int(data.get("cycle", 0))
                prog = float(data.get("progress", 0.0))
                status = data.get("status", "Running")
            else:
                parts = line.split(",")
                if len(parts) >= 5:
                    sample_ref_id = parts[0].strip()
                    if parts[1].strip() in ['Evidence', 'Reference']:
                        sample_ref_type = parts[1].strip()
                        temp = float(parts[2].strip())
                        cycle = int(parts[3].strip())
                        prog = float(parts[4].strip())
                        status = parts[5].strip() if len(parts) >= 6 else "Running"
                    else:
                        temp = float(parts[1].strip())
                        cycle = int(parts[2].strip())
                        prog = float(parts[3].strip())
                        status = parts[4].strip()

            if sample_ref_id:
                database.add_pcr_telemetry(sample_ref_id, sample_ref_type, temp, cycle, prog, status)
                
                # Check PCR completion transition
                if status.lower() == "complete" or cycle >= 30:
                    database.update_sample_status(sample_ref_id, sample_ref_type, "PCR Complete")
                    blockchain.add_custody_block(sample_ref_id, sample_ref_type, "PCR completed")

        except Exception as e:
            print(f"[Hardware Parse Warning] Payload '{line}': {e}")

    def start_pcr_run(self, sample_ref_id, sample_ref_type='Evidence'):
        """
        Initiates a PCR thermal run for an Evidence or Reference sample.
        Sends start command to physical ESP32 if connected, otherwise starts simulation thread.
        """
        # Update sample status & append custody blocks
        database.update_sample_status(sample_ref_id, sample_ref_type, "PCR Running")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        blockchain.add_custody_block(sample_ref_id, sample_ref_type, "Received by device", now_str)
        blockchain.add_custody_block(sample_ref_id, sample_ref_type, "PCR started", now_str)

        if self.serial_conn and self.serial_conn.is_open:
            try:
                cmd = f"START:{sample_ref_id}:{sample_ref_type}\n"
                self.serial_conn.write(cmd.encode('utf-8'))
                return True, f"Hardware command sent to ESP32 on {self.port}"
            except Exception as e:
                print(f"[Hardware Serial Error] {e}")

        # Launch hardware simulator thread
        sim_thread = threading.Thread(
            target=self._run_simulated_pcr, 
            args=(sample_ref_id, sample_ref_type), 
            daemon=True
        )
        sim_thread.start()
        return True, f"PCR thermal run initiated for {sample_ref_id} ({sample_ref_type} - Hardware Simulator Active)"

    def _run_simulated_pcr(self, sample_ref_id, sample_ref_type):
        """
        Simulates realistic 30-cycle PCR thermal cycling:
        Denaturation (95°C) -> Annealing (55°C) -> Extension (72°C).
        Emits telemetry records every 0.15s for rapid live demo presentation.
        """
        total_cycles = 30
        
        try:
            with self.simulation_lock:
                self.active_simulations[sample_ref_id] = {
                    'active': True,
                    'current_cycle': 0,
                    'current_temp': 25.0,
                    'progress': 0.0,
                    'status': 'Running'
                }

            # Initial baseline thermal ramp
            for temp in [25.0, 50.0, 75.0, 95.0]:
                database.add_pcr_telemetry(sample_ref_id, sample_ref_type, temp, 0, 0.0, 'Ramping')
                time.sleep(0.1)

            for cycle in range(1, total_cycles + 1):
                with self.simulation_lock:
                    if not self.active_simulations.get(sample_ref_id, {}).get('active', True):
                        break

                # 3 PCR Thermal Stages
                stages = [
                    (95.0, "Denaturation"),
                    (55.0, "Annealing"),
                    (72.0, "Extension")
                ]

                for target_temp, stage_name in stages:
                    progress = round((cycle / total_cycles) * 100.0, 1)
                    actual_temp = round(target_temp + (time.time() % 0.6 - 0.3), 1)
                    
                    database.add_pcr_telemetry(
                        sample_ref_id,
                        sample_ref_type,
                        actual_temp, 
                        cycle, 
                        progress, 
                        f"Running ({stage_name})"
                    )

                    with self.simulation_lock:
                        if sample_ref_id in self.active_simulations:
                            self.active_simulations[sample_ref_id]['current_cycle'] = cycle
                            self.active_simulations[sample_ref_id]['current_temp'] = actual_temp
                            self.active_simulations[sample_ref_id]['progress'] = progress

                    time.sleep(0.12)  # Fast, smooth thermal cycle speed for hackathon presentation

            # Finalize PCR Run
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            database.add_pcr_telemetry(sample_ref_id, sample_ref_type, 25.0, total_cycles, 100.0, 'Complete')
            database.update_sample_status(sample_ref_id, sample_ref_type, 'PCR Complete')
            blockchain.add_custody_block(sample_ref_id, sample_ref_type, 'PCR completed', now_str)

            with self.simulation_lock:
                if sample_ref_id in self.active_simulations:
                    self.active_simulations[sample_ref_id]['status'] = 'Complete'
                    self.active_simulations[sample_ref_id]['active'] = False

        except Exception as e:
            print(f"[Hardware Simulation Error] Exception during PCR run for {sample_ref_id}: {e}")

# Global hardware manager instance
hardware_manager = HardwareManager()
