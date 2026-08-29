from resume.resume_agent import process_resume

class FakeUpload:
    def __init__(self, path):
        self.name = path
        self._file = open(path, "rb")
    def __getattr__(self, attr):
        return getattr(self._file, attr)

path = input("Enter path to your resume file: ").strip()
fake = FakeUpload(path)

result = process_resume(fake, user_id=1)
print(result)