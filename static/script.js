"use strict";

const API_BASE = "/api/listings";

// ===== CLOSURE (kept from HW1) =====
// Tracks how many times the form has been successfully submitted this session.
const submissionCounter = (() => {
    let count = 0;
    return () => ++count;
})();

// ===== DOM REFERENCES =====
const form = document.getElementById("listingForm");
const editingIdInput = document.getElementById("editingId");
const submitButton = document.getElementById("submitButton");
const cancelEditButton = document.getElementById("cancelEditButton");

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const clearSearchButton = document.getElementById("clearSearchButton");

const loadingState = document.getElementById("loadingState");
const emptyState = document.getElementById("emptyState");
const errorState = document.getElementById("errorState");
const errorMessage = document.getElementById("errorMessage");
const retryButton = document.getElementById("retryButton");
const listingList = document.getElementById("listingList");

// ===== STATE HELPERS =====
const showState = (state) => {
    loadingState.classList.add("hidden");
    emptyState.classList.add("hidden");
    errorState.classList.add("hidden");
    listingList.classList.add("hidden");

    if (state === "loading") loadingState.classList.remove("hidden");
    if (state === "empty") emptyState.classList.remove("hidden");
    if (state === "error") errorState.classList.remove("hidden");
    if (state === "list") listingList.classList.remove("hidden");
};

// ===== FETCH + RENDER LISTINGS =====
const fetchListings = async (query) => {
    showState("loading");
    submitButton.disabled = true;

    const url = query ? `${API_BASE}?q=${encodeURIComponent(query)}` : API_BASE;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}`);
        }
        // CONCEPT: JSON.parse happens implicitly via response.json()
        const data = await response.json();

        if (!data.length) {
            showState("empty");
        } else {
            renderListings(data);
            showState("list");
        }
    } catch (err) {
        console.error("Failed to load listings:", err);
        errorMessage.textContent = `Couldn't load listings: ${err.message}. Check that the backend is running.`;
        showState("error");
    } finally {
        submitButton.disabled = false;
    }
};

const renderListings = (data) => {
    listingList.innerHTML = "";
    data.forEach((listing) => {
        // CONCEPT: DESTRUCTURING
        const { id, propertyAddress, monthlyRent, propertyCategory } = listing;

        const li = document.createElement("li");
        li.setAttribute("id", `listing-${id}`);

        const titleDiv = document.createElement("div");
        titleDiv.className = "listing-title";
        titleDiv.textContent = `${propertyAddress} (#${id})`;

        const metaDiv = document.createElement("div");
        metaDiv.className = "listing-meta";
        metaDiv.textContent = `${propertyCategory} | ${monthlyRent}`;

        const actionsDiv = document.createElement("div");
        actionsDiv.className = "listing-actions";

        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.textContent = "Edit";
        editBtn.className = "edit-button";
        editBtn.onclick = handleEdit.bind(null, listing);

        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.textContent = "Delete";
        deleteBtn.className = "delete-button";
        deleteBtn.onclick = handleDelete.bind(null, id);

        actionsDiv.appendChild(editBtn);
        actionsDiv.appendChild(deleteBtn);

        li.appendChild(titleDiv);
        li.appendChild(metaDiv);
        li.appendChild(actionsDiv);
        listingList.appendChild(li);
    });
};

// ===== EDIT FLOW =====
const handleEdit = (listing) => {
    editingIdInput.value = listing.id;
    document.getElementById("propertyAddress").value = listing.propertyAddress;
    document.getElementById("monthlyRent").value = listing.monthlyRent;
    document.getElementById("submitterEmail").value = listing.submitterEmail;
    document.getElementById("listingDescription").value = listing.listingDescription;
    document.getElementById("propertyCategory").value = listing.propertyCategory;
    document.getElementById("agreeTerms").checked = true;

    submitButton.textContent = "Update Listing";
    cancelEditButton.classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
};

const exitEditMode = () => {
    editingIdInput.value = "";
    submitButton.textContent = "Submit Listing";
    cancelEditButton.classList.add("hidden");
    form.reset();
};

cancelEditButton.addEventListener("click", exitEditMode);

// ===== DELETE FLOW =====
const handleDelete = async (id) => {
    try {
        const response = await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
        if (!response.ok && response.status !== 204) {
            throw new Error(`Server responded with status ${response.status}`);
        }
        console.log(`Deleted listing: ${id}`);
        await fetchListings();
    } catch (err) {
        console.error("Failed to delete listing:", err);
        alert(`Couldn't delete listing: ${err.message}`);
    }
};

// ===== VALIDATION (kept from HW1, arrow function) =====
const validateForm = () => {
    const description = document.getElementById("listingDescription").value.trim();
    const agreeTerms = document.getElementById("agreeTerms").checked;

    if (description.length <= 25) {
        alert("Property description must be longer than 25 characters.");
        return false;
    }

    if (!agreeTerms) {
        alert("You must agree to the terms and conditions before submitting.");
        return false;
    }

    return true;
};

// ===== CREATE / UPDATE SUBMIT =====
form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!validateForm()) return;

    const listingData = {
        propertyAddress: document.getElementById("propertyAddress").value,
        monthlyRent: document.getElementById("monthlyRent").value,
        submitterEmail: document.getElementById("submitterEmail").value,
        listingDescription: document.getElementById("listingDescription").value,
        propertyCategory: document.getElementById("propertyCategory").value,
    };

    // CONCEPT: JSON.stringify — logged for the same visibility HW1 required
    console.log("Listing Data (String):", JSON.stringify(listingData));

    const editingId = editingIdInput.value;
    const isEditing = Boolean(editingId);

    try {
        const response = await fetch(isEditing ? `${API_BASE}/${editingId}` : API_BASE, {
            method: isEditing ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(listingData),
        });

        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}`);
        }

        const saved = await response.json();

        // CONCEPT: SPREAD OPERATOR
        const updatedListingData = { ...saved, submissionDate: new Date().toISOString() };
        console.log("Saved listing (with submissionDate):", updatedListingData);

        const currentCount = submissionCounter();
        console.log(isEditing ? "Total Edits So Far:" : "Total Submissions So Far:", currentCount);

        exitEditMode();
        await fetchListings();
    } catch (err) {
        console.error("Failed to save listing:", err);
        alert(`Couldn't save listing: ${err.message}`);
    }
});

// ===== SEARCH =====
searchButton.addEventListener("click", () => fetchListings(searchInput.value.trim()));
searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        fetchListings(searchInput.value.trim());
    }
});
clearSearchButton.addEventListener("click", () => {
    searchInput.value = "";
    fetchListings();
});

// ===== RETRY (error state) =====
retryButton.addEventListener("click", () => fetchListings(searchInput.value.trim()));

// ===== INITIAL LOAD =====
fetchListings();
