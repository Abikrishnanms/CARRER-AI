from resume.resume_parser import extract_resume_text

class FakeUpload:
    def __init__(self, path):
        self.name = path
        self._file = open(path, "rb")
    def __getattr__(self, attr):
        return getattr(self._file, attr)

path = input("Enter path to your resume file (PDF or DOCX): ").strip()
fake = FakeUpload(path)
text = extract_resume_text(fake)
print(f"Extracted {len(text)} characters")
print("---")
print(text[:500])