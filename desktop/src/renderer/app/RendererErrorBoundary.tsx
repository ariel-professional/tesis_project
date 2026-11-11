import { Component, type ErrorInfo, type ReactNode } from "react";

export class RendererErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error("Renderer error", error, info); }
  render() {
    if (this.state.error !== null) return <main className="shell-error" role="alert"><h1>No se pudo mostrar la aplicación</h1><p>{this.state.error.message}</p></main>;
    return this.props.children;
  }
}
