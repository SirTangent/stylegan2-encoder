from celery import Celery
from runtime import Runtime

import os
import requests
from PIL import Image
from math import floor
from scraper import scrape_har_extract

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1 import ArrayUnion

cred_obj = firebase_admin.credentials.Certificate('face-of-the-team-firebase-adminsdk-sumqm-ee99a4d5fa.json')
default_app = firebase_admin.initialize_app(cred_obj, {
    'projectId': 'face-of-the-team',
    'storageBucket': 'face-of-the-team.appspot.com'
})

db = firestore.client(default_app)
c_jobs = db.collection('jobs')
bucket = storage.bucket()

celery = Celery('fott_server', broker='redis://localhost:6379')

ROOT_DIR = "face_queue/"

def remove_transparency(im, bg_colour=(255, 255, 255)):

    # Only process if image has transparency (http://stackoverflow.com/a/1963146)
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):

        # Need to convert to RGBA if LA format due to a bug in PIL (http://stackoverflow.com/a/1963146)
        alpha = im.convert('RGBA').split()[-1]

        # Create a new background image of our matt color.
        # Must be RGBA because paste requires both images have the same format
        # (http://stackoverflow.com/a/8720632  and  http://stackoverflow.com/a/9459208)
        bg = Image.new("RGBA", im.size, bg_colour + (255,))
        bg.paste(im, mask=alpha)
        return bg

    else:
        return im

@celery.task
def job_exec(jobid):

    print(f"Accepting jobId: {jobid}")

    # Pull information on job

    doc = c_jobs.document(jobid)
    job = doc.get()

    if not job.exists:
        return "jobid is not associated with an active job", 404

    job_data = job.to_dict()

    # Job found and retrieved at this point
    name = job_data['name']
    src = job_data['src']
    job_id = job.id

    # Create directory structure
    path = os.path.join(ROOT_DIR, f"{job_id}/")
    if not os.path.isdir(path):
        os.mkdir(path)

    results = scrape_har_extract(src, output_folder=path)

    if results <= 0:
        return results

    images_aligned = os.path.join(path, "images-aligned/")
    if not os.path.isdir(images_aligned):
        os.mkdir(images_aligned)

    print(f"[{name}] Align Images...")
    align_images(job_id)

    for file in os.listdir(images_aligned):
        png = Image.open(os.path.join(images_aligned, file)).convert('RGB')
        png.save(os.path.join(images_aligned, file))

        blob = bucket.blob(os.path.join(f"faces/{job_id}/", file))
        with open(os.path.join(images_aligned, file), 'rb') as f:
            blob.upload_from_file(f)

        doc.update( {
            "imgs": ArrayUnion([f"test {file}"])
        })

        # print(f"resaved {file}")

    print(f"[{name}] Project Images...")
    project_images(job_id)

    print(f"[{name}] Generate Average...")
    generate_average(job_id)

    print(f"[{name}] Job Complete!")

@celery.task
def align_images(job_id):
    runtime = Runtime(os.path.join(ROOT_DIR, f"{job_id}/"))
    runtime.run_aligner()

@celery.task
def project_images(job_id):
    runtime = Runtime(os.path.join(ROOT_DIR, f"{job_id}/"))
    runtime.run_projector()

@celery.task
def generate_average(job_id):
    runtime = Runtime(os.path.join(ROOT_DIR, f"{job_id}/"))
    runtime.run_averager()