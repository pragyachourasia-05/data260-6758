import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8458",
  withCredentials: true,
});

export async function login(email, password) {
  const response = await api.post("/auth/login", {
    email,
    password,
  });

  return response.data;
}

export async function logout() {
  const response = await api.post("/auth/logout");
  return response.data;
}

export async function me() {
  const response = await api.get("/auth/me");
  return response.data;
}

export async function fetchListings() {
  const response = await api.get("/listings");
  return response.data;
}

export async function fetchListingById(id) {
  const response = await api.get(`/listings/${id}`);
  return response.data;
}

export async function createListing(payload) {
  const response = await api.post("/listings", payload);
  return response.data;
}

export async function updateListing(id, payload) {
  const response = await api.put(`/listings/${id}`, payload);
  return response.data;
}

export async function deleteListing(id) {
  const response = await api.delete(`/listings/${id}`);
  return response.data;
}