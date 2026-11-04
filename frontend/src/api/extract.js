
export async function extractRequirements(customerText) {
  const text = customerText.trim();

  if (text.length < 5) {
    throw new Error(
      "Enter a meaningful customer description."
    );
  }

  if (text.length > 1200) {
    throw new Error(
      "Customer description must be 1200 characters or fewer."
    );
  }

  let response;

  try {
    response = await fetch("/api/requirements/extract", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        customer_text: text,
      }),
    });
  } catch {
    throw new Error(
      "Cannot connect to the AI extraction API. " +
      "Check that FastAPI is running."
    );
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof body?.detail === "string"
        ? body.detail
        : `AI extraction failed (HTTP ${response.status}).`;

    throw new Error(message);
  }

  if (
    !body?.requirements ||
    !body?.field_states ||
    !body?.evidence ||
    !Array.isArray(body?.review_notes)
  ) {
    throw new Error(
      "The AI returned an unexpected response."
    );
  }

  return body;
}
