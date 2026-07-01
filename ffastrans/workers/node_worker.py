"""Node worker - runs on worker nodes and connects to master for job processing."""
import os
import sys
import time
import json
import logging
import urllib.request
from ..core.config import REMOTE_NODE_URL, HOSTNAME, MAX_CONCURRENT_JOBS, NODE_REGISTRATION_INTERVAL

logger = logging.getLogger("ffastrans.worker")


class NodeWorker:
    def __init__(self, master_url: str):
        self.master_url = master_url.rstrip("/")
        self.hostname = HOSTNAME
        self.max_jobs = MAX_CONCURRENT_JOBS
        self.active = False

    def register(self):
        data = json.dumps({
            "name": self.hostname,
            "hostname": self.hostname,
            "ip": "0.0.0.0",
            "port": int(os.getenv("FFASTRANS_API_PORT", "8080")),
            "groups": ["default"],
            "max_jobs": self.max_jobs,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self.master_url}/api/hosts/register",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Registered with master: {resp.status}")
                self.active = True
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            self.active = False

    def heartbeat(self):
        try:
            req = urllib.request.Request(f"{self.master_url}/api/hosts/heartbeat")
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            logger.warning("Heartbeat failed")

    def get_pending_job(self):
        try:
            req = urllib.request.Request(f"{self.master_url}/api/jobs/active")
            with urllib.request.urlopen(req, timeout=10) as resp:
                jobs = json.loads(resp.read())
                for job in jobs:
                    if job["state"] == "queued" and job.get("host", "") == "":
                        return job
        except Exception:
            pass
        return None

    def run(self):
        logger.info(f"Starting worker node: {self.hostname} -> {self.master_url}")
        while True:
            try:
                if not self.active:
                    self.register()
                else:
                    self.heartbeat()

                job = self.get_pending_job()
                if job:
                    logger.info(f"Processing job: {job['id']}")
                    self.process_job(job)

            except KeyboardInterrupt:
                logger.info("Worker shutting down")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")

            time.sleep(NODE_REGISTRATION_INTERVAL)

    def process_job(self, job):
        logger.info(f"Processing job {job['id']} for workflow {job['wf_id']}")
        try:
            req = urllib.request.Request(
                f"{self.master_url}/api/jobs/{job['id']}",
                data=json.dumps({"action": "resume"}).encode(),
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.error(f"Failed to process job: {e}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    master_url = os.getenv("FFASTRANS_REMOTE_NODE_URL", REMOTE_NODE_URL)
    if not master_url:
        logger.error("FFASTRANS_REMOTE_NODE_URL not set")
        sys.exit(1)

    worker = NodeWorker(master_url)
    worker.run()


if __name__ == "__main__":
    main()
