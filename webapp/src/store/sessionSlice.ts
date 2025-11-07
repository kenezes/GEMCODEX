import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface SessionState {
  token: string | null;
  userName: string | null;
}

const initialState: SessionState = {
  token: null,
  userName: null
};

const sessionSlice = createSlice({
  name: "session",
  initialState,
  reducers: {
    setSession(state, action: PayloadAction<SessionState>) {
      state.token = action.payload.token;
      state.userName = action.payload.userName;
    },
    clearSession(state) {
      state.token = null;
      state.userName = null;
    }
  }
});

export const { setSession, clearSession } = sessionSlice.actions;
export default sessionSlice.reducer;
