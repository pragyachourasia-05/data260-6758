import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { api } from "../../api/axios";

const getErrorMessage = (error, fallback) =>
  error.response?.data?.detail || error.message || fallback;

export const fetchListings = createAsyncThunk(
  "listings/fetchListings",
  async (_, thunkAPI) => {
    try {
      const response = await api.get("/listings");
      return response.data;
    } catch (error) {
      return thunkAPI.rejectWithValue(
        getErrorMessage(error, "Failed to fetch listings")
      );
    }
  }
);

export const createListing = createAsyncThunk(
  "listings/createListing",
  async (payload, thunkAPI) => {
    try {
      const response = await api.post("/listings", payload);
      return response.data;
    } catch (error) {
      return thunkAPI.rejectWithValue(
        getErrorMessage(error, "Failed to create listing")
      );
    }
  }
);

export const updateListing = createAsyncThunk(
  "listings/updateListing",
  async ({ id, payload }, thunkAPI) => {
    try {
      const response = await api.put(`/listings/${id}`, payload);
      return response.data;
    } catch (error) {
      return thunkAPI.rejectWithValue(
        getErrorMessage(error, "Failed to update listing")
      );
    }
  }
);

export const deleteListing = createAsyncThunk(
  "listings/deleteListing",
  async (id, thunkAPI) => {
    try {
      await api.delete(`/listings/${id}`);
      return id;
    } catch (error) {
      return thunkAPI.rejectWithValue(
        getErrorMessage(error, "Failed to delete listing")
      );
    }
  }
);

const listingsSlice = createSlice({
  name: "listings",

  initialState: {
    items: [],
    loading: false,
    error: null,
  },

  reducers: {},

  extraReducers: (builder) => {
    builder
      .addCase(fetchListings.pending, (state) => {
        state.loading = true;
        state.error = null;
      })

      .addCase(fetchListings.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload;
      })

      .addCase(fetchListings.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })

      .addCase(createListing.fulfilled, (state, action) => {
        state.items.push(action.payload);
      })

      .addCase(createListing.rejected, (state, action) => {
        state.error = action.payload;
      })

      .addCase(updateListing.fulfilled, (state, action) => {
        const index = state.items.findIndex(
          (listing) => listing.id === action.payload.id
        );

        if (index !== -1) {
          state.items[index] = action.payload;
        }
      })

      .addCase(updateListing.rejected, (state, action) => {
        state.error = action.payload;
      })

      .addCase(deleteListing.fulfilled, (state, action) => {
        state.items = state.items.filter(
          (listing) => listing.id !== action.payload
        );
      })

      .addCase(deleteListing.rejected, (state, action) => {
        state.error = action.payload;
      });
  },
});

export default listingsSlice.reducer;