"use strict";

// ===== CONCEPT: FORM VALIDATION (ARROW FUNCTION) =====
// a) Description must be more than 25 characters
// b) Terms and conditions checkbox must be checked
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

// ===== CONCEPT: CLOSURE =====
// Tracks how many times the form has been successfully submitted.
// The 'count' variable stays private inside the closure and persists
// across calls, only accessible through the returned function.
const submissionCounter = (() => {
    let count = 0;
    return () => ++count;
})();

// ===== EVENT LISTENER =====
document.getElementById("listingForm").addEventListener("submit", (e) => {
    e.preventDefault(); // Stop the page from reloading on submit

    // Validate first; stop here if invalid
    if (!validateForm()) return;

    // ===== COLLECT FORM DATA =====
    const propertyAddress = document.getElementById("propertyAddress").value;
    const monthlyRent = document.getElementById("monthlyRent").value;
    const submitterEmail = document.getElementById("submitterEmail").value;
    const listingDescription = document.getElementById("listingDescription").value;
    const propertyCategory = document.getElementById("propertyCategory").value;

    const listingData = {
        propertyAddress,
        monthlyRent,
        submitterEmail,
        listingDescription,
        propertyCategory,
    };

    // ===== CONCEPT: JSON.stringify =====
    // Convert the listing object into a JSON string and log it
    const jsonListingData = JSON.stringify(listingData);
    console.log("Listing Data (String):", jsonListingData);

    // ===== CONCEPT: JSON.parse =====
    // Convert the JSON string back into a JavaScript object
    const parsedListingData = JSON.parse(jsonListingData);
    console.log("Listing Data (Parsed):", parsedListingData);

    // ===== CONCEPT: DESTRUCTURING =====
    // Extract the primary field (propertyAddress) and email field
    // directly from the parsed object
    const { propertyAddress: address, submitterEmail: email } = parsedListingData;
    console.log("Primary Field (Property Address):", address);
    console.log("Email Field:", email);

    // ===== CONCEPT: SPREAD OPERATOR =====
    // Copy all fields from the parsed object and add a new
    // submissionDate field with the current date and time
    const updatedListingData = {
        ...parsedListingData,
        submissionDate: new Date().toISOString(),
    };
    console.log("Updated Listing Data (with submissionDate):", updatedListingData);

    // ===== CONCEPT: CLOSURE IN ACTION =====
    const currentCount = submissionCounter();
    console.log("Total Submissions So Far:", currentCount);

    // ===== UPDATE UI =====
    addListingToUI({ ...updatedListingData, id: `listing-${currentCount}` });

    alert("Listing submitted successfully!");

    // Clear form inputs
    document.getElementById("listingForm").reset();
    document.getElementById("propertyAddress").focus();
});

// ===== HELPER FUNCTION FOR UI =====
const addListingToUI = (listing) => {
    const { propertyAddress, monthlyRent, propertyCategory, id } = listing;

    const listItem = document.createElement("li");
    listItem.setAttribute("id", id);
    listItem.textContent = `${propertyAddress} | ${propertyCategory} | ${monthlyRent}`;

    const deleteButton = document.createElement("button");
    deleteButton.textContent = "Delete";
    deleteButton.onclick = handleDelete.bind(null, id); // Using bind

    listItem.appendChild(deleteButton);
    document.getElementById("listingList").appendChild(listItem);
};

// ===== DELETE HANDLER =====
const handleDelete = function (id) {
    const listingElement = document.getElementById(id);
    console.log(`Deleting listing: ${id}`);
    listingElement.remove();
};
