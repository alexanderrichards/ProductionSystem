function worksheet_to_excel_rows(sheet, xlsx) {
    var rows = xlsx.utils.sheet_to_json(sheet, {header: 1, raw: true, defval: null, blankrows: true});
    var has_value = function(value) {
        return value !== null && value !== undefined && value !== "";
    };
    if (!rows.length || !rows[0].some(has_value)) {
        throw new Error("The first worksheet must contain a header row.");
    }

    var headers = rows[0].map(function(header) {
        return typeof header === "string" ? header.trim() : "";
    });
    var seen = new Set();
    headers.forEach(function(header, index) {
        if (!header) {
            throw new Error(`Column ${index + 1} must have a JSON field name as its header.`);
        }
        if (seen.has(header)) {
            throw new Error(`Duplicate column header: ${header}.`);
        }
        if (["__proto__", "constructor", "prototype"].includes(header)) {
            throw new Error(`Unsupported column header: ${header}.`);
        }
        seen.add(header);
    });

    var excel_rows = [];
    rows.slice(1).forEach(function(row, index) {
        if (!row.some(has_value)) return;
        if (row.slice(headers.length).some(has_value)) {
            throw new Error(`Row ${index + 2} contains data in a column without a header.`);
        }
        var excel_row = {};
        headers.forEach(function(header, column) {
            if (has_value(row[column])) excel_row[header] = row[column];
        });
        excel_rows.push(excel_row);
    });
    if (!excel_rows.length) {
        throw new Error("The first worksheet must contain at least one data row.");
    }
    return excel_rows;
}

class ParametricJobUpload {
    constructor(input,
                status,
                submit_button,
                summary,
                form,
                create_request) {
        if (!input || typeof input.setCustomValidity !== "function" || !status || !submit_button) {
            throw new TypeError("ParametricJobUpload requires a file input, status element and submit button.");
        }
        if (typeof create_request !== "function") {
            throw new TypeError("ParametricJobUpload requires a synchronous create_request callback.");
        }
        form = $(form);
        if (form.length !== 1 || form[0].tagName !== "FORM") {
            throw new TypeError("ParametricJobUpload requires exactly one form.");
        }
        this.input = input;
        this.status = status;
        this.submit_button = submit_button;
        this.summary = summary;
        this.excel_rows = null;
        this.payload = null;
        this.form = form;
        this.submitting = false;
        this.version = 0;
        this.clearSummary();
        // this.create_request = create_request.bind(this, form);  // first argument binds to this in the function not the first function arg.
        this.create_request = create_request.bind(null, form);  // remove access to 'this' within the create_request function to avoid accidental mutation of the ParametricJobUpload's excel_rows data.
        submit_button.disabled = true;
        input.addEventListener("change", () => this.read());
        form.on("input change", ":input[name]", () => this.refreshRequest());
    }

    clearSummary() {
        if (!this.summary) return;
        this.summary.textContent = "";
        this.summary.hidden = true;
    }

    refreshRequest() {
        if (this.submitting) return;
        this.payload = null;
        this.submit_button.disabled = true;
        this.clearSummary();
        if (!this.excel_rows) return;
        try {
            // Deep-copy the JSON-compatible rows so hook transformations cannot corrupt later refreshes.
            var payload = this.create_request(JSON.parse(JSON.stringify(this.excel_rows)));
            // Preparation is synchronous; a Promise is not a usable request object.
            if (payload && typeof payload.then === "function") {
                // Observe rejected async hooks to avoid an unhandled rejection after refusing their result.
                Promise.resolve(payload).catch(error => {
                    console.error("Rejected asynchronous request setup hook failed.", error);
                });
                throw new TypeError("The request setup hook must be synchronous.");
            }
            // Normalize to the wire representation: omit undefined properties and detach hook-owned objects.
            // Circular references and BigInt throw here and are handled by the preparation error handler.
            payload = JSON.parse(JSON.stringify(payload, function(key, value) {
                if (typeof value === "number" && !Number.isFinite(value)) {
                    // JSON would silently replace NaN/Infinity with null, concealing invalid numeric input.
                    throw new TypeError("The request contains a non-finite number.");
                }
                return value;
            }));
            // Require the plain request shape; model-specific field validation remains the server's job.
            if (!payload || typeof payload !== "object" || Array.isArray(payload) ||
                !Array.isArray(payload.parametric_jobs) ||
                payload.parametric_jobs.some(job => !job || typeof job !== "object" || Array.isArray(job))) {
                throw new Error("The request setup hook must return a request with a parametric_jobs array of objects.");
            }
            // Freeze nested objects and arrays too; a shallow freeze would leave individual jobs mutable.
            // Later refreshes replace this snapshot rather than editing it, keeping preview and submission aligned.
            var freeze = function(value) {
                if (value && typeof value === "object") {
                    Object.values(value).forEach(freeze);
                    Object.freeze(value);
                }
            };
            freeze(payload);
            this.payload = payload;
            this.showSummary();
            this.submit_button.disabled = false;
        } catch (error) {
            this.payload = null;
            this.submit_button.disabled = true;
            this.clearSummary();
            console.error("Failed to prepare new request.", error);
            if (this.summary) {
                var message = document.createElement("p");
                message.className = "text-danger";
                message.setAttribute("role", "alert");
                message.textContent = `Unable to prepare request preview: ${error instanceof Error ? error.message : String(error)}`;
                this.summary.appendChild(message);
                this.summary.hidden = false;
            } else {
                this.status.textContent = `Unable to prepare request: ${error instanceof Error ? error.message : String(error)}`;
                this.status.className = "form-text text-danger";
            }
        }
    }

    prepareSubmission() {
        if (this.submitting) return null;
        if (!this.excel_rows || !this.payload) {
            throw new Error("Prepare a valid request preview before submitting the request.");
        }
        var request_json = JSON.stringify({request: this.payload});
        this.submitting = true;
        this.submit_button.disabled = true;
        this.input.disabled = true;
        return request_json;
    }

    allowRetrySubmission() {
        this.submitting = false;
        this.input.disabled = false;
        this.refreshRequest();
    }

    showSummary() {
        if (!this.summary) return;
        var fields = new Set();
        this.payload.parametric_jobs.forEach(function(job) {
            Object.keys(job).forEach(field => fields.add(field));
        });
        var heading = document.createElement("h5");
        heading.textContent = "Parametricjob preview";
        var count = document.createElement("p");
        count.textContent = `${this.payload.parametric_jobs.length} parametricjob(s), ${fields.size} field(s). ` +
            "Defaults to the first and last jobs; choose one job number to inspect it instead. " +
            "Job numbers start at 1 in the request's parametric_jobs list, not Excel row numbers. " +
            "Missing values are omitted from JSON; " +
            "Only fields present in the submitted jobs are listed. Long values are shortened here only.";
        this.summary.appendChild(heading);
        this.summary.appendChild(count);
        this.summary.hidden = false;
        if (!this.payload.parametric_jobs.length) return;
        var controls = document.createElement("div");
        controls.className = "mb-2";
        var label = document.createElement("label");
        label.textContent = "Job number: ";
        var selection = document.createElement("input");
        selection.type = "text";
        selection.inputMode = "numeric";
        selection.placeholder = `1 to ${this.payload.parametric_jobs.length}`;
        selection.className = "form-control form-control-sm d-inline-block w-auto mx-2";
        label.appendChild(selection);
        controls.appendChild(label);
        var choose = document.createElement("button");
        choose.type = "button";
        choose.className = "btn btn-sm btn-primary mr-2";
        choose.textContent = "Show job";
        controls.appendChild(choose);
        var reset = document.createElement("button");
        reset.type = "button";
        reset.className = "btn btn-sm btn-outline-secondary";
        reset.textContent = "Show first and last";
        controls.appendChild(reset);
        var error = document.createElement("div");
        error.className = "text-danger";
        error.setAttribute("role", "alert");
        controls.appendChild(error);
        var wrapper = document.createElement("div");
        wrapper.className = "table-responsive";
        var show_selected = () => {
            var value = selection.value.trim();
            var number = Number(value);
            if (!/^[0-9]+$/.test(value) || !Number.isSafeInteger(number) ||
                number < 1 || number > this.payload.parametric_jobs.length) {
                error.textContent = `Enter one whole job number from 1 to ${this.payload.parametric_jobs.length}; ranges are not supported.`;
                selection.setAttribute("aria-invalid", "true");
                return;
            }
            error.textContent = "";
            selection.removeAttribute("aria-invalid");
            this.renderSummaryTable(fields, wrapper, number);
        };
        choose.addEventListener("click", show_selected);
        selection.addEventListener("keydown", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                show_selected();
            }
        });
        reset.addEventListener("click", () => {
            selection.value = "";
            error.textContent = "";
            selection.removeAttribute("aria-invalid");
            this.renderSummaryTable(fields, wrapper);
        });
        this.renderSummaryTable(fields, wrapper);
        this.summary.appendChild(controls);
        this.summary.appendChild(wrapper);
        this.summary.hidden = false;
    }

    renderSummaryTable(fields, wrapper, job_number = null) {
        var table = document.createElement("table");
        table.className = "table table-sm table-bordered mb-0";
        var head = table.createTHead().insertRow();
        var labels = ["Field", job_number === null ? "First job (#1)" : `Job (#${job_number})`];
        var examples = [this.payload.parametric_jobs[job_number === null ? 0 : job_number - 1]];
        if (job_number === null && this.payload.parametric_jobs.length > 1) {
            labels.push(`Last job (#${this.payload.parametric_jobs.length})`);
            examples.push(this.payload.parametric_jobs[this.payload.parametric_jobs.length - 1]);
        }
        labels.forEach(function(label) {
            var cell = document.createElement("th");
            cell.scope = "col";
            cell.textContent = label;
            head.appendChild(cell);
        });
        var body = table.createTBody();
        fields.forEach(function(field) {
            var row = body.insertRow();
            var label = document.createElement("th");
            label.scope = "row";
            label.textContent = field;
            row.appendChild(label);
            examples.forEach(function(job) {
                var cell = row.insertCell();
                if (!Object.prototype.hasOwnProperty.call(job, field)) {
                    cell.textContent = "(omitted)";
                    cell.className = "text-muted";
                    return;
                }
                var value = JSON.stringify(job[field]);
                cell.textContent = value.length > 200 ? value.slice(0, 200) + "..." : value;
                cell.style.whiteSpace = "pre-wrap";
                cell.style.overflowWrap = "anywhere";
            });
        });
        wrapper.textContent = "";
        wrapper.appendChild(table);
    }

    async read() {
        if (this.submitting) return;
        var version = ++this.version;
        this.excel_rows = null;
        this.payload = null;
        this.clearSummary();
        this.submit_button.disabled = true;
        this.status.className = "form-text text-muted";
        this.input.setCustomValidity("");
        var file = this.input.files[0];
        if (!file) {
            this.status.textContent = "Choose an Excel file to load its rows.";
            return;
        }
        this.status.textContent = "Reading Excel file...";
        try {
            if (!/\.(xlsx|xls)$/i.test(file.name)) {
                throw new Error("Choose an .xlsx or .xls file.");
            }
            if (typeof XLSX === "undefined") {
                throw new Error("The Excel reader could not be loaded. Reload the page and try again.");
            }
            var buffer = await file.arrayBuffer();
            if (version !== this.version) return;
            var workbook = XLSX.read(buffer, {type: "array"});
            if (!workbook.SheetNames.length) {
                throw new Error("The workbook does not contain any worksheets.");
            }
            var sheet_name = workbook.SheetNames[0];
            this.excel_rows = worksheet_to_excel_rows(workbook.Sheets[sheet_name], XLSX);
            this.status.textContent = `Loaded ${this.excel_rows.length} Excel row(s) from "${sheet_name}".`;
            this.status.className = "form-text text-success";
            this.refreshRequest();
        } catch (error) {
            // A replaced file must not overwrite the latest upload's state.
            if (version !== this.version) return;
            this.excel_rows = null;
            this.payload = null;
            this.submit_button.disabled = true;
            this.clearSummary();
            console.error("Failed to read Excel rows.", error);
            this.status.textContent = `Unable to load Excel file: ${error instanceof Error ? error.message : String(error)}`;
            this.status.className = "form-text text-danger";
            this.input.setCustomValidity(this.status.textContent);
        }
    }
}
