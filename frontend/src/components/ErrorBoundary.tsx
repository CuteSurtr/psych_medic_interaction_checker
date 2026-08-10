import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  /** Shown in the fallback so the user knows which panel failed. */
  label?: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Contains a render failure to one section.
 *
 * React unmounts the entire tree when a render throws, so a single bad value
 * anywhere below the root blanks the whole page. The analysis view renders
 * eight independent panels from eight independent API responses, and one of
 * them failing should cost that panel, not the application.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(
      `[${this.props.label ?? "section"}] render failed:`,
      error,
      info.componentStack,
    );
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3">
        <p className="text-sm font-semibold text-rose-800">
          {this.props.label ?? "This section"} could not be displayed.
        </p>
        <p className="mt-1 text-xs text-rose-700">
          The rest of the page is unaffected. Details are in the browser
          console.
        </p>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-xs text-rose-600">
          {error.message}
        </pre>
      </div>
    );
  }
}
