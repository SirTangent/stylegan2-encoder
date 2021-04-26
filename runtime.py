import os
from subprocess import getoutput

from uuid import uuid1 as uuid


def create_dir(path):
    try:
        if not os.path.exists(path):
            os.mkdir(path)
    except Exception as e:
        print(e)

class Runtime:

    def __init__(self, img_dir="images/", generate_folder=False):
        if generate_folder:
            # Generate job UUID
            job_uuid = uuid()
            job_dir = f"{img_dir}{job_uuid}"

            self.dir = job_dir
            self.uuid = job_uuid
        else:
            self.dir = img_dir

        create_dir(self.dir)

    def run_aligner(self, src_dir="", target_dir=""):
        if src_dir == "":
            src_dir = self.dir
        if target_dir == "":
            target_dir = os.path.join(src_dir, "images-aligned")

        create_dir(target_dir)

        # Run asynchronously
        return getoutput(f"python align_images.py {src_dir} {target_dir}")

    def run_encoder(self, aligned_dir="", gen_dir="", latent_dir="", output_video=True):
        if aligned_dir == "":
            aligned_dir = os.path.join(self.dir, "images-aligned")
        if gen_dir == "":
            gen_dir = os.path.join(self.dir, "images-generated")
        if latent_dir == "":
            latent_dir = os.path.join(self.dir, "images-latent")

        create_dir(gen_dir)
        create_dir(latent_dir)

        # Run asynchronously
        print(getoutput(
            f"python encode_images.py --clipping_threshold 10.0 --batch_size=1 --output_video={'True' if output_video else 'False'} {aligned_dir} {gen_dir} {latent_dir}"))

    def run_projector(self, aligned_dir="", gen_dir=""):
        if aligned_dir == "":
            aligned_dir = os.path.join(self.dir, "images-aligned")
        if gen_dir == "":
            gen_dir = os.path.join(self.dir, "images-generated")

        create_dir(gen_dir)

        print(getoutput(f"python project_images.py {aligned_dir} {gen_dir}"))

    def run_averager(self, latent_dir="", output_file=""):
        if latent_dir == "":
            latent_dir = os.path.join(self.dir, "images-generated")
        if output_file == "":
            output_file = os.path.join(self.dir, "images-average")

        # Split path
        head, tail = os.path.split(output_file)

        # TODO: Validate appropriate path name

        # Run asynchronously
        print(getoutput(f"python generate_average.py {latent_dir} {f'--dst_dir {head}' if head else ''} --name={tail}"))

    def run_pipeline(self, src_dir="", aligned_dir="", gen_dir="", latent_dir="", output_file=""):
        return [
            self.run_aligner(src_dir, aligned_dir),
            # TODO: Add duplicate remover
            self.run_projector(aligned_dir, gen_dir),
            self.run_averager(latent_dir, output_file)
        ]