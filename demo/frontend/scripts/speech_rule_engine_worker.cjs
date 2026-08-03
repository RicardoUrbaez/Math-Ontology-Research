const path = require("path");
const sre = require("speech-rule-engine");

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const mathml = chunks.join("").trim();
  if (!mathml) throw new Error("No MathML input was supplied.");

  const packageRoot = path.dirname(require.resolve("speech-rule-engine/package.json"));
  await sre.setupEngine({
    json: path.join(packageRoot, "lib", "mathmaps"),
    locale: "en",
    domain: "clearspeak",
    style: "default",
    modality: "speech"
  });
  await sre.engineReady();
  const spoken = String(sre.toSpeech(mathml) || "").trim();
  process.stdout.write(JSON.stringify({ spoken }));
}

main().catch((error) => {
  process.stderr.write(String(error && error.message ? error.message : error));
  process.exitCode = 1;
});
