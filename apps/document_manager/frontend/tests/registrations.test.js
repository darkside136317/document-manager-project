import { describe, expect, it } from "vitest";
import {
  absoluteLink, badges, describeRequest, isResetRequest, REGISTRATIONS_ROUTE, registrationTone, setPendingBadge,
  STATUS_FILTERS, TYPE_FILTERS,
} from "../src/lib/registrations.js";

describe("registration queue helpers", () => {
  it("builds the link an officer hands over from the relative path the server returns", () => {
    expect(absoluteLink("/dat-mat-khau?key=abc", "https://lt.example")).toBe("https://lt.example/dat-mat-khau?key=abc");
    expect(absoluteLink("https://other.example/x", "https://lt.example")).toBe("https://other.example/x");
  });

  it("tells sign-ups from password requests", () => {
    expect(isResetRequest({ request_type: "Quên mật khẩu" })).toBe(true);
    expect(isResetRequest({ request_type: "Đăng ký tài khoản" })).toBe(false);
    expect(isResetRequest(null)).toBe(false);
  });

  it("describes what approving does", () => {
    const row = { full_name: "An", email: "an@x.vn" };
    expect(describeRequest({ ...row, request_type: "Đăng ký tài khoản" })).toBe("Tạo tài khoản độc giả cho An <an@x.vn>");
    expect(describeRequest({ ...row, request_type: "Quên mật khẩu" })).toBe("Cấp lại mật khẩu cho An <an@x.vn>");
  });

  it("colours the statuses", () => {
    expect(registrationTone("Mới")).toBe("warning");
    expect(registrationTone("Đã duyệt")).toBe("success");
    expect(registrationTone("Từ chối")).toBe("danger");
    expect(registrationTone("?")).toBe("muted");
  });

  it("keeps the sidebar counter in step with the queue", () => {
    setPendingBadge(3);
    expect(badges[REGISTRATIONS_ROUTE]).toBe(3);
    setPendingBadge(0);
    expect(badges[REGISTRATIONS_ROUTE]).toBeUndefined();
  });

  it("offers the queue first and every status last", () => {
    expect(STATUS_FILTERS[0].value).toBe("Mới");
    expect(STATUS_FILTERS.at(-1).value).toBe("");
    expect(TYPE_FILTERS[0].value).toBe("");
  });
});
