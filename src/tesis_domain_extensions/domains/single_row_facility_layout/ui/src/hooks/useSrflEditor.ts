import { useReducer } from "react";
import type { SrflEditorDraft } from "../model/editor-draft.types";
import { EditorActionKind, editorReducer } from "../model/editor-reducer";

export function useSrflEditor() {
  const [state, dispatch] = useReducer(editorReducer, { draft: null, dirty: false, revision: 0 });
  return {
    ...state,
    open: (draft: SrflEditorDraft) => dispatch({ type: EditorActionKind.Open, draft }),
    update: (draft: SrflEditorDraft) => dispatch({ type: EditorActionKind.Update, draft }),
    clear: () => dispatch({ type: EditorActionKind.Clear }),
  };
}

