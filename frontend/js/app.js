const input = document.getElementById("photo-input");
const button = document.getElementById("preview-btn");
const result = document.getElementById("result-image");

input.addEventListener("change", () => {
  button.disabled = input.files.length === 0;
});

button.addEventListener("click", async () => {
  const formData = new FormData();
  formData.append("image", input.files[0]);
  button.disabled = true;
  try {
    const response = await fetch("http://localhost:8000/api/preview", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    const blob = await response.blob();
    result.src = URL.createObjectURL(blob);
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
});
