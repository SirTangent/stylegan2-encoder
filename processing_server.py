from flask import Flask, request
import tasks
import os

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_face():
    data = request.get_json()

    # Validate body
    if data is None:
        return "Request must have a JSON body", 400
    if "jobid" not in data:
        return "Request is missing jobId", 400

    jobid = data['jobid']

    tasks.job_exec.apply_async(args=[jobid])

    return f'{data["jobid"]} => [Processing]', 200
