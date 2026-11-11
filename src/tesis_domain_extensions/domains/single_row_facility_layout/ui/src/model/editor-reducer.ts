import type { SrflEditorDraft } from "./editor-draft.types";

export enum EditorActionKind { Open = "open", Update = "update", Clear = "clear" }
export type EditorState = { draft: SrflEditorDraft | null; dirty: boolean; revision: number };
export type EditorAction =
  | { type: EditorActionKind.Open; draft: SrflEditorDraft }
  | { type: EditorActionKind.Update; draft: SrflEditorDraft }
  | { type: EditorActionKind.Clear };

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case EditorActionKind.Open: return { draft: action.draft, dirty: false, revision: state.revision + 1 };
    case EditorActionKind.Update: return { draft: action.draft, dirty: true, revision: state.revision + 1 };
    case EditorActionKind.Clear: return { draft: null, dirty: false, revision: state.revision + 1 };
  }
}

