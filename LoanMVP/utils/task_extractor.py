
def extract_tasks(text):
    tasks = []
    for line in text.split("\n"):
        if any(x in line.lower() for x in ["follow", "call", "send", "verify", "request"]):
            tasks.append(line.strip())
    return tasks