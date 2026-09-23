import { Component } from "react";

// Si lo que envuelve falla al dibujarse, muestra `fallback` en su lugar en vez de dejar
// toda la app en blanco (p. ej. un navegador viejo sin alguna función de JS).
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error(error);
  }

  render() {
    return this.state.error ? (this.props.fallback ?? null) : this.props.children;
  }
}
