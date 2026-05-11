import os
import subprocess

result = subprocess.run(
    ['python', '-c', 'import os; print(os.environ.get("GROQ_API_KEY"))'],
    capture_output=True,
    text=True
)
print("Child process sees:", result.stdout)