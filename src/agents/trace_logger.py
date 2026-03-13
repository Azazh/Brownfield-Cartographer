import json
import datetime
import threading

class TraceLogger:
    """
    Production-grade trace logger for Cartographer agent actions.
    Writes JSONL records: timestamp, agent, action, input, output, evidence, confidence.
    Thread-safe for multi-agent use.
    """
    def __init__(self, log_path):
        self.log_path = log_path
        self.lock = threading.Lock()

    def log(self, agent, action, input_data=None, output_data=None, evidence=None, confidence=None, extra=None):
        record = {
            "timestamp": datetime.datetime.utcnow().isoformat() + 'Z',
            "agent": agent,
            "action": action,
            "input": input_data,
            "output": output_data,
            "evidence": evidence,
            "confidence": confidence,
        }
        if extra:
            record.update(extra)
        with self.lock:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
