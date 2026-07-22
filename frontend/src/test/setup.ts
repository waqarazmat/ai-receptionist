import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Reset the DOM between tests so state doesn't leak between suites — the
// default @testing-library/react cleanup happens on `unmount` but that's
// often forgotten when a test renders and asserts synchronously.
afterEach(() => cleanup());
