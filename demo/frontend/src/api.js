async function request(url, options, action) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (cause) {
    const error = new Error(
      `Could not reach the MathOntoSpeak backend while ${action}. The PDF and form are still here; confirm the API is running on port 8000, then try again.`
    );
    error.connectionError = true;
    error.cause = cause;
    throw error;
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${action} failed with ${response.status}.`);
  }

  return response.json();
}

export async function analyzePaper(payload) {
  return request("/api/paper/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }, "starting the analysis");
}

export async function createPaperJob(payload) {
  return request("/api/paper/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }, "queueing PDF extraction");
}

export async function getPaperJob(jobId) {
  return request(
    `/api/paper/jobs/${encodeURIComponent(jobId)}`,
    undefined,
    "checking PDF extraction progress"
  );
}

export async function analyzePaperJob(payload, onProgress = () => {}) {
  const started = await createPaperJob(payload);
  const deadline = Date.now() + 15 * 60 * 1000;
  let job = started;
  let connectionFailures = 0;
  while (Date.now() < deadline) {
    onProgress(job);
    if (job.status === "complete") return job.result;
    if (job.status === "failed") throw new Error(job.error || "Paper analysis failed.");
    await new Promise((resolve) => window.setTimeout(resolve, 750));
    try {
      job = await getPaperJob(started.job_id);
      connectionFailures = 0;
    } catch (error) {
      if (!error.connectionError || connectionFailures >= 7) throw error;
      connectionFailures += 1;
      onProgress({
        status: "processing",
        stage: `reconnecting_to_backend_${connectionFailures}_of_8`,
        progress: job.progress || 0
      });
      await new Promise((resolve) => window.setTimeout(resolve, 750));
    }
  }
  throw new Error("Paper analysis exceeded the 15-minute browser wait limit.");
}

export async function getHealth() {
  return request("/health", undefined, "checking system health");
}

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read PDF file."));
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",", 2)[1] : value);
    };
    reader.readAsDataURL(file);
  });
}
