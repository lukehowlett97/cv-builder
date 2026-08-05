(function () {
  "use strict";

  var statusBadge = document.getElementById("status-badge");
  var generateBtn = document.getElementById("generate-btn");
  var outputNameInput = document.getElementById("output-name");
  var cvMarkdownInput = document.getElementById("cv-markdown");
  var coverTextInput = document.getElementById("cover-text");
  var processingIndicator = document.getElementById("processing-indicator");
  var errorBox = document.getElementById("error-box");
  var resultBox = document.getElementById("result-box");
  var resultTimestamp = document.getElementById("result-timestamp");
  var resultFiles = document.getElementById("result-files");

  var appMain = document.getElementById("app-main");
  var focusPreviewBtn = document.getElementById("focus-preview-btn");
  var restoreEditorBtn = document.getElementById("restore-editor-btn");

  var tabPreviewBtn = document.getElementById("tab-preview-btn");
  var tabFilesBtn = document.getElementById("tab-files-btn");
  var tabPreview = document.getElementById("tab-preview");
  var tabFiles = document.getElementById("tab-files");
  var previewFormatToggle = document.getElementById("preview-format-toggle");
  var previewMarkdownBtn = document.getElementById("preview-markdown-btn");
  var previewPdfBtn = document.getElementById("preview-pdf-btn");
  var filesTree = document.getElementById("files-tree");
  var previewEmpty = document.getElementById("preview-empty");
  var previewContainer = document.getElementById("preview-container");
  var previewLabel = document.getElementById("preview-label");
  var pdfPreview = document.getElementById("pdf-preview");
  var markdownPreview = document.getElementById("markdown-preview");
  var openPreviewBtn = document.getElementById("open-preview-btn");
  var copyMarkdownBtn = document.getElementById("copy-markdown-btn");

  var loadFileBtn = document.getElementById("load-file-btn");
  var markdownFileInput = document.getElementById("markdown-file-input");
  var useSampleBtn = document.getElementById("use-sample-btn");
  var pullPreviewBtn = document.getElementById("pull-preview-btn");
  var clearBtn = document.getElementById("clear-btn");
  var openOutputBtn = document.getElementById("open-output-btn");
  var headerOptionInputs = Array.prototype.slice.call(
    document.querySelectorAll("[data-frontmatter-key]")
  );
  var headerFieldKeys = ["name", "headline", "location", "email", "linkedin", "github", "website"];
  var requiredHeaderFields = ["name", "headline", "location", "email"];

  var generating = false;
  var markdownRequestId = 0;
  var previewMarkdownText = null;
  var previewMarkdownPromise = null;
  var previewFiles = {
    pdfUrl: null,
    pdfName: "",
    markdownUrl: null,
    markdownName: "",
    runName: null,
  };

  function frontmatterBounds(lines) {
    if (!lines.length || lines[0].trim() !== "---") {
      return null;
    }
    for (var i = 1; i < lines.length; i += 1) {
      if (lines[i].trim() === "---") {
        return { end: i };
      }
    }
    return null;
  }

  function decodeYamlScalar(rawValue) {
    var value = rawValue.trim();
    if (value.length >= 2 && value[0] === '"' && value[value.length - 1] === '"') {
      try {
        return JSON.parse(value);
      } catch (error) {
        return value.slice(1, -1);
      }
    }
    if (value.length >= 2 && value[0] === "'" && value[value.length - 1] === "'") {
      return value.slice(1, -1).replace(/''/g, "'");
    }
    return value;
  }

  function headerValues() {
    var values = {};
    headerOptionInputs.forEach(function (input) {
      values[input.dataset.frontmatterKey] = input.value.trim();
    });
    return values;
  }

  function syncHeaderOptionsFromMarkdown() {
    var lines = cvMarkdownInput.value.split(/\r?\n/);
    var bounds = frontmatterBounds(lines);
    var values = {};
    headerFieldKeys.forEach(function (key) { values[key] = ""; });

    if (bounds) {
      lines.slice(1, bounds.end).forEach(function (line) {
        var match = line.match(/^([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$/);
        if (match && headerFieldKeys.indexOf(match[1]) !== -1) {
          values[match[1]] = decodeYamlScalar(match[2]);
        }
      });
    }

    headerOptionInputs.forEach(function (input) {
      input.value = values[input.dataset.frontmatterKey] || "";
    });
  }

  function syncMarkdownFromHeaderOptions() {
    var lines = cvMarkdownInput.value.split(/\r?\n/);
    var bounds = frontmatterBounds(lines);
    var values = headerValues();

    if (!bounds) {
      var hasHeaderValue = headerFieldKeys.some(function (key) { return Boolean(values[key]); });
      if (!hasHeaderValue) {
        return;
      }
      var newFrontmatter = ["---"];
      headerFieldKeys.forEach(function (key) {
        if (values[key] || requiredHeaderFields.indexOf(key) !== -1) {
          newFrontmatter.push(key + ": " + JSON.stringify(values[key]));
        }
      });
      newFrontmatter.push("---", "");
      cvMarkdownInput.value = newFrontmatter.join("\n") + cvMarkdownInput.value.replace(/^\s+/, "");
      return;
    }

    headerFieldKeys.forEach(function (key) {
      var pattern = new RegExp("^" + key + "\\s*:");
      var lineIndex = -1;
      for (var i = 1; i < bounds.end; i += 1) {
        if (pattern.test(lines[i])) {
          lineIndex = i;
          break;
        }
      }
      var keepField = Boolean(values[key]) || requiredHeaderFields.indexOf(key) !== -1;
      if (lineIndex !== -1 && keepField) {
        lines[lineIndex] = key + ": " + JSON.stringify(values[key]);
      } else if (lineIndex !== -1) {
        lines.splice(lineIndex, 1);
        bounds.end -= 1;
      } else if (keepField) {
        lines.splice(bounds.end, 0, key + ": " + JSON.stringify(values[key]));
        bounds.end += 1;
      }
    });

    cvMarkdownInput.value = lines.join("\n");
  }

  function setStatus(text, state) {
    statusBadge.textContent = text;
    statusBadge.className = "status-badge status-" + (state || "checking");
  }

  function showError(message, detail) {
    errorBox.classList.remove("hidden");
    errorBox.innerHTML = "";
    var p = document.createElement("p");
    p.textContent = message;
    errorBox.appendChild(p);
    if (detail) {
      var pre = document.createElement("pre");
      pre.textContent = detail;
      errorBox.appendChild(pre);
    }
    errorBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function hideError() {
    errorBox.classList.add("hidden");
    errorBox.innerHTML = "";
  }

  function setProcessing(processing, stage) {
    generating = processing;
    if (processing) {
      generateBtn.disabled = true;
      generateBtn.textContent = "Generating…";
      processingIndicator.classList.remove("hidden");
      processingIndicator.textContent = stage || "Generating…";
    } else {
      generateBtn.disabled = false;
      generateBtn.textContent = "Generate CV";
      processingIndicator.classList.add("hidden");
      processingIndicator.textContent = "";
    }
  }

  function switchTab(tab) {
    var showPreview = tab === "preview";
    tabPreviewBtn.classList.toggle("active", showPreview);
    tabFilesBtn.classList.toggle("active", !showPreview);
    tabPreview.classList.toggle("hidden", !showPreview);
    tabFiles.classList.toggle("hidden", showPreview);
    previewFormatToggle.classList.toggle("hidden", !showPreview);
  }

  function setFormatButtons(mode) {
    var markdownActive = mode === "markdown";
    previewMarkdownBtn.classList.toggle("active", markdownActive);
    previewMarkdownBtn.setAttribute("aria-pressed", String(markdownActive));
    previewPdfBtn.classList.toggle("active", !markdownActive);
    previewPdfBtn.setAttribute("aria-pressed", String(!markdownActive));
    previewMarkdownBtn.disabled = !previewFiles.markdownUrl;
    previewPdfBtn.disabled = !previewFiles.pdfUrl;
  }

  function loadPreviewMarkdown() {
    if (!previewFiles.markdownUrl) {
      return Promise.reject(new Error("No generated Markdown is available"));
    }
    if (previewMarkdownText !== null) {
      return Promise.resolve(previewMarkdownText);
    }
    if (previewMarkdownPromise) {
      return previewMarkdownPromise;
    }

    var markdownUrl = previewFiles.markdownUrl;
    previewMarkdownPromise = fetch(markdownUrl + "?t=" + Date.now())
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Could not load Markdown");
        }
        return response.text();
      })
      .then(function (markdown) {
        if (previewFiles.markdownUrl === markdownUrl) {
          previewMarkdownText = markdown;
        }
        return markdown;
      })
      .finally(function () {
        if (previewFiles.markdownUrl === markdownUrl) {
          previewMarkdownPromise = null;
        }
      });
    return previewMarkdownPromise;
  }

  function showPreviewMode(mode) {
    if (mode === "markdown" && !previewFiles.markdownUrl) {
      mode = "pdf";
    } else if (mode === "pdf" && !previewFiles.pdfUrl) {
      mode = "markdown";
    }

    if (!previewFiles.pdfUrl && !previewFiles.markdownUrl) {
      return;
    }

    setFormatButtons(mode);
    previewEmpty.classList.add("hidden");
    previewContainer.classList.remove("hidden");
    switchTab("preview");

    if (mode === "markdown") {
      var requestId = ++markdownRequestId;
      pdfPreview.classList.add("hidden");
      markdownPreview.classList.remove("hidden");
      markdownPreview.textContent = "Loading Markdown…";
      previewLabel.textContent = previewFiles.markdownName;
      openPreviewBtn.href = previewFiles.markdownUrl;
      openPreviewBtn.textContent = "Open Markdown in new tab";
      copyMarkdownBtn.classList.remove("hidden");

      loadPreviewMarkdown()
        .then(function (markdown) {
          if (requestId === markdownRequestId) {
            markdownPreview.textContent = markdown;
          }
        })
        .catch(function () {
          if (requestId === markdownRequestId) {
            markdownPreview.textContent = "Could not load the generated Markdown.";
          }
        });
      return;
    }

    markdownRequestId += 1;
    markdownPreview.classList.add("hidden");
    pdfPreview.classList.remove("hidden");
    var cacheBust = "?t=" + Date.now() + "&v=" + Math.random().toString(36).slice(2, 8);
    pdfPreview.src = previewFiles.pdfUrl + cacheBust + "#toolbar=0&navpanes=0";
    previewLabel.textContent = previewFiles.pdfName;
    openPreviewBtn.href = previewFiles.pdfUrl;
    openPreviewBtn.textContent = "Open PDF in new tab";
    copyMarkdownBtn.classList.add("hidden");
  }

  function setPreviewFiles(files, mode) {
    previewFiles = files;
    previewMarkdownText = null;
    previewMarkdownPromise = null;
    pullPreviewBtn.disabled = !previewFiles.markdownUrl;
    showPreviewMode(mode || "pdf");
  }

  function showResult(data) {
    hideError();
    resultFiles.innerHTML = "";
    resultTimestamp.textContent = "Generated " + (data.generated_at || new Date().toISOString());

    var files = data.files || [];
    files.forEach(function (file) {
      var li = document.createElement("li");
      var row = document.createElement("div");
      row.className = "result-file-row";

      var info = document.createElement("div");
      info.className = "result-file-info";

      var name = document.createElement("div");
      name.className = "result-file-name";
      name.textContent = file.name;
      info.appendChild(name);

      var path = document.createElement("div");
      path.className = "result-file-path";
      path.textContent = file.path;
      info.appendChild(path);

      var actions = document.createElement("div");
      actions.className = "result-file-actions";

      var openBtn = document.createElement("a");
      openBtn.className = "btn btn-small";
      openBtn.href = file.url;
      openBtn.target = "_blank";
      openBtn.rel = "noopener";
      openBtn.textContent = "Open file";
      actions.appendChild(openBtn);

      if (file.type === "pdf") {
        var openPdf = document.createElement("a");
        openPdf.className = "btn btn-small";
        openPdf.href = file.url;
        openPdf.target = "_blank";
        openPdf.rel = "noopener";
        openPdf.textContent = "Open PDF in new tab";
        actions.appendChild(openPdf);
      }

      var copyBtn = document.createElement("button");
      copyBtn.className = "btn btn-small";
      copyBtn.type = "button";
      copyBtn.textContent = "Copy path";
      copyBtn.addEventListener("click", function () {
        copyText(file.path);
      });
      actions.appendChild(copyBtn);

      row.appendChild(info);
      row.appendChild(actions);
      li.appendChild(row);
      resultFiles.appendChild(li);
    });

    resultBox.classList.remove("hidden");
    loadRuns();

    if (data.preview_url || data.markdown_url) {
      setPreviewFiles({
        pdfUrl: data.preview_url,
        pdfName: data.name + " / " + data.pdf_path.split("/").pop(),
        markdownUrl: data.markdown_url,
        markdownName: data.name + " / " + data.markdown_path.split("/").pop(),
        runName: data.name,
      }, "pdf");
    }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () {
        fallbackCopy(text);
      });
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
    } catch (e) {
      // Ignore copy failures in restricted contexts.
    }
    document.body.removeChild(textarea);
  }

  function renderTree(runs) {
    filesTree.innerHTML = "";

    if (!runs.length) {
      var empty = document.createElement("p");
      empty.className = "files-empty";
      empty.textContent = "No generated files found yet.";
      filesTree.appendChild(empty);
      return;
    }

    runs.forEach(function (run) {
      var group = document.createElement("div");
      group.className = "tree-run";

      var header = document.createElement("div");
      header.className = "tree-run-header";
      header.textContent = run.name;
      group.appendChild(header);

      var path = document.createElement("div");
      path.className = "tree-run-path";
      path.textContent = run.path;
      group.appendChild(path);

      var files = document.createElement("div");
      files.className = "tree-files";

      var pdfFile = run.files.find(function (file) { return file.type === "pdf"; });
      var markdownFile = run.files.find(function (file) { return file.type === "md"; });
      var runPreviewFiles = {
        pdfUrl: pdfFile ? (pdfFile.preview_url || pdfFile.url) : null,
        pdfName: pdfFile ? run.name + " / " + pdfFile.name : "",
        markdownUrl: markdownFile ? markdownFile.url : null,
        markdownName: markdownFile ? run.name + " / " + markdownFile.name : "",
        runName: run.name,
      };

      run.files.forEach(function (file) {
        var btn = document.createElement("button");
        btn.className = "tree-file";
        btn.title = file.url;

        var type = document.createElement("span");
        type.className = "file-type type-" + file.type;
        type.textContent = file.type;
        btn.appendChild(type);

        var name = document.createElement("span");
        name.className = "file-name";
        name.textContent = file.name;
        btn.appendChild(name);

        btn.addEventListener("click", function () {
          if (file.type === "pdf") {
            setPreviewFiles(runPreviewFiles, "pdf");
          } else if (file.type === "md") {
            hideError();
            setPreviewFiles(runPreviewFiles, "markdown");
          } else {
            showError("DOCX files cannot be previewed inline. Open the file from the runs directory.");
          }
        });

        files.appendChild(btn);
      });

      group.appendChild(files);
      filesTree.appendChild(group);
    });
  }

  function loadRuns() {
    fetch("/api/runs")
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        renderTree(data.runs || []);
      })
      .catch(function () {
        filesTree.innerHTML = "";
        var p = document.createElement("p");
        p.className = "files-empty";
        p.textContent = "Could not load existing files.";
        filesTree.appendChild(p);
      });
  }

  function checkStatus() {
    fetch("/api/status")
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.ok) {
          setStatus("Ready — pandoc & xelatex available", "ok");
          generateBtn.disabled = false;
        } else {
          setStatus(
            "Missing: " + data.missing.join(", "),
            "error"
          );
          generateBtn.disabled = true;
        }
      })
      .catch(function () {
        setStatus("Could not reach backend", "error");
        generateBtn.disabled = true;
      });
  }

  function generate() {
    if (generating) {
      return;
    }

    syncMarkdownFromHeaderOptions();
    var markdown = cvMarkdownInput.value;
    var name = outputNameInput.value.trim();
    var coverText = coverTextInput.value;

    if (!markdown.trim()) {
      showError("Please paste CV Markdown before generating.");
      return;
    }
    if (!name) {
      showError("Please provide an output name.");
      return;
    }

    hideError();
    setProcessing(true, "Validating Markdown…");

    fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        markdown: markdown,
        name: name,
        cover_text: coverText,
      }),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, status: response.status, data: data };
        });
      })
      .then(function (result) {
        if (result.ok) {
          setProcessing(true, "Complete");
          showResult(result.data);
        } else {
          showError(
            result.data.error || "Generation failed.",
            result.data.detail || null
          );
        }
      })
      .catch(function () {
        showError("Network error while generating.");
      })
      .finally(function () {
        setProcessing(false);
      });
  }

  function loadMarkdownFile(file) {
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function (event) {
      cvMarkdownInput.value = event.target.result;
      syncHeaderOptionsFromMarkdown();
      hideError();
    };
    reader.onerror = function () {
      showError("Could not read the selected file.");
    };
    reader.readAsText(file);
  }

  function useSample() {
    fetch("/api/sample")
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Failed to load sample");
        }
        return response.json();
      })
      .then(function (data) {
        cvMarkdownInput.value = data.markdown || "";
        syncHeaderOptionsFromMarkdown();
        hideError();
      })
      .catch(function () {
        showError("Could not load the sample markdown.");
      });
  }

  function pullFromPreview() {
    pullPreviewBtn.disabled = true;
    pullPreviewBtn.textContent = "Pulling…";
    loadPreviewMarkdown()
      .then(function (markdown) {
        cvMarkdownInput.value = markdown;
        syncHeaderOptionsFromMarkdown();
        hideError();
        cvMarkdownInput.focus();
      })
      .catch(function () {
        showError("Could not pull Markdown from the current preview.");
      })
      .finally(function () {
        pullPreviewBtn.disabled = !previewFiles.markdownUrl;
        pullPreviewBtn.textContent = "Pull from preview";
      });
  }

  function copyPreviewMarkdown() {
    copyMarkdownBtn.disabled = true;
    loadPreviewMarkdown()
      .then(function (markdown) {
        copyText(markdown);
        copyMarkdownBtn.textContent = "Copied";
        window.setTimeout(function () {
          copyMarkdownBtn.textContent = "Copy to clipboard";
        }, 1500);
      })
      .catch(function () {
        showError("Could not copy the generated Markdown.");
      })
      .finally(function () {
        copyMarkdownBtn.disabled = false;
      });
  }

  function clearEditor() {
    cvMarkdownInput.value = "";
    coverTextInput.value = "";
    syncHeaderOptionsFromMarkdown();
    hideError();
    cvMarkdownInput.focus();
  }

  function focusPreview() {
    appMain.classList.add("focus-preview");
    focusPreviewBtn.classList.add("hidden");
    restoreEditorBtn.classList.remove("hidden");
  }

  function restoreEditor() {
    appMain.classList.remove("focus-preview");
    focusPreviewBtn.classList.remove("hidden");
    restoreEditorBtn.classList.add("hidden");
  }

  tabPreviewBtn.addEventListener("click", function () { switchTab("preview"); });
  tabFilesBtn.addEventListener("click", function () { switchTab("files"); });
  previewMarkdownBtn.addEventListener("click", function () { showPreviewMode("markdown"); });
  previewPdfBtn.addEventListener("click", function () { showPreviewMode("pdf"); });
  copyMarkdownBtn.addEventListener("click", copyPreviewMarkdown);
  generateBtn.addEventListener("click", generate);
  focusPreviewBtn.addEventListener("click", focusPreview);
  restoreEditorBtn.addEventListener("click", restoreEditor);

  loadFileBtn.addEventListener("click", function () {
    markdownFileInput.click();
  });
  markdownFileInput.addEventListener("change", function () {
    loadMarkdownFile(markdownFileInput.files[0]);
    markdownFileInput.value = "";
  });
  useSampleBtn.addEventListener("click", useSample);
  pullPreviewBtn.addEventListener("click", pullFromPreview);
  clearBtn.addEventListener("click", clearEditor);
  cvMarkdownInput.addEventListener("input", syncHeaderOptionsFromMarkdown);
  headerOptionInputs.forEach(function (input) {
    input.addEventListener("input", syncMarkdownFromHeaderOptions);
  });

  openOutputBtn.addEventListener("click", function () {
    fetch("/api/open-output", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run: previewFiles.runName }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data.ok) {
          showError(data.error || "Could not open the output folder.");
        }
      })
      .catch(function () {
        showError("Could not open the output folder.");
      });
  });

  document.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      generate();
    }
  });

  checkStatus();
  loadRuns();
})();
