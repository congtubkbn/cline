import os
import fitz  # PyMuPDF

def split_large_pdfs_fast(input_folder: str, max_size_mb: float = 3.9, threshold_mb: float = 4.0):
    if not os.path.exists(input_folder):
        print(f"Lỗi: Thư mục '{input_folder}' không tồn tại!")
        return

    print(f"Đang quét thư mục: {input_folder}\n" + "="*50)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_folder, filename)
            file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
            
            if file_size_mb < threshold_mb:
                print(f"[-] Bỏ qua '{filename}' ({file_size_mb:.2f}MB) - Dưới ngưỡng {threshold_mb}MB.")
                continue
                
            print(f"[+] Đang xử lý tốc độ cao: '{filename}' ({file_size_mb:.2f}MB)")
            
            base_name = os.path.splitext(filename)[0]
            output_subfolder = os.path.join(input_folder, base_name)
            if not os.path.exists(output_subfolder):
                os.makedirs(output_subfolder)
            
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            start_page = 0
            part_num = 1
            
            while start_page < total_pages:
                # -- THUẬT TOÁN TÌM KIẾM NHỊ PHÂN (BINARY SEARCH) --
                low = start_page + 1
                high = total_pages
                best_end = start_page + 1 # Mặc định lấy ít nhất 1 trang
                
                while low <= high:
                    mid = (low + high) // 2
                    
                    # Cắt tạm file để kiểm tra
                    temp_doc = fitz.open()
                    temp_doc.insert_pdf(doc, from_page=start_page, to_page=mid - 1)
                    
                    # TỐI ƯU 1: LƯU VÀO RAM THAY VÌ Ổ CỨNG
                    # Dùng deflate=True để nén kích thước sát với thực tế
                    pdf_bytes = temp_doc.tobytes(deflate=True)
                    temp_doc.close()
                    
                    current_size_mb = len(pdf_bytes) / (1024 * 1024)
                    
                    if current_size_mb <= max_size_mb:
                        # Kích thước an toàn -> Lưu mốc này lại, thử cộng thêm trang
                        best_end = mid
                        low = mid + 1
                    else:
                        # Kích thước vượt mức -> Phải lùi số trang lại
                        high = mid - 1

                # -- LƯU FILE CHÍNH THỨC RA Ổ CỨNG --
                current_part_path = os.path.join(output_subfolder, f"{base_name}_part_{part_num}.pdf")
                final_part_doc = fitz.open()
                final_part_doc.insert_pdf(doc, from_page=start_page, to_page=best_end - 1)
                
                # TỐI ƯU 2: Chỉ nén triệt để (garbage=4) ở bước lưu ra đĩa cuối cùng này
                final_part_doc.save(current_part_path, garbage=4, deflate=True)
                final_part_doc.close()
                
                actual_size = os.path.getsize(current_part_path) / (1024 * 1024)
                
                if best_end - start_page == 1 and actual_size > max_size_mb:
                    print(f"   -> Cảnh báo: Trang {best_end} chứa ảnh quá nặng ({actual_size:.2f}MB), bắt buộc lưu.")
                else:
                    print(f"   -> Đã lưu: part_{part_num}.pdf ({actual_size:.2f}MB) | {best_end - start_page} trang.")
                
                start_page = best_end
                part_num += 1

            doc.close()
            print(f"[*] Hoàn thành chia nhỏ '{filename}'.\n")
            
    print("--- HOÀN TẤT QUÁ TRÌNH ---")

if __name__ == "__main__":
    # --- ĐIỀN ĐƯỜNG DẪN THƯ MỤC CHỨA FILE PDF VÀO DƯỚI ĐÂY ---
    INPUT_FOLDER_STRING = r"C:\Users\VK MIT\Downloads\2803"
    
    split_large_pdfs_fast(INPUT_FOLDER_STRING)