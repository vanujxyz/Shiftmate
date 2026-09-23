import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest does not expose test globals here, so Testing Library cannot auto-clean between tests.
afterEach(() => cleanup());
