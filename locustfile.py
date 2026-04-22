from locust import HttpUser, between, task
import os

class FastAPIUser(HttpUser):
    wait_time = between(1, 2)
    host = "http://127.0.0.1:8000"

    def on_start(self):
        file_path = os.path.join(os.path.dirname(__file__), "assets", "12345.png")
        self.image = open(file_path, "rb")
        self.student_id = None

    @task
    def create_student(self):
        self.image.seek(0) 

        with self.client.post(
            "/student",
            data={
                "name": "Test",
                "age": "22",
                "course": "Python",
                "mark": "80",
                "email": "test@gmail.com"
            },
            files={
                "image": ("12345.png", self.image, "image/png")
            },
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                self.student_id = response.json().get("id")
            else:
                response.failure(f"{response.status_code}: {response.text}")

    @task(2)
    def get_single_student(self):
        if not self.student_id:
            return 

        with self.client.get(f"/students/{self.student_id}", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"{response.status_code}: {response.text}")

    @task
    def get_all_students(self):
        with self.client.get("/students", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"{response.status_code}: {response.text}")