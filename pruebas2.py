import requests
import os

url = "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"
output_folder = "css"
os.makedirs(output_folder, exist_ok=True)
output_path = os.path.join(output_folder, "animate.min.css")

response = requests.get(url)
if response.status_code == 200:
    with open(output_path, "wb") as f:
        f.write(response.content)
    print(f"Animate.css guardado en: {output_path}")
else:
    print("Error descargando Animate.css")