BASE_10_UNITS = (
	(pow(1000, 0), "B"),  # Byte
	(pow(1000, 1), "KB"),  # Kilobyte
	(pow(1000, 2), "MB"),  # Megabyte
	(pow(1000, 3), "GB"),  # Gigabyte
	(pow(1000, 4), "TB"),  # Terabyte
)

BASE_2_UNITS = (
	(pow(1024, 0), "B"),  # Byte
	(pow(1024, 1), "KiB"),  # Kibibyte
	(pow(1024, 2), "MiB"),  # Mebibyte
	(pow(1024, 3), "GiB"),  # Gibibyte
	(pow(1024, 4), "TiB"),  # Tebibyte
)


def convert_size(size: int, base_10: bool) -> tuple[int | float, str]:
	"""
	Convert size in bytes to the largest possible unit

	:param size: Size in bytes
	:param base_10: Whether to use base 10 or 2 units
	:return: New size and unit
	"""
	units = BASE_10_UNITS if base_10 else BASE_2_UNITS
	factor, unit = units[0]
	for next_factor, next_unit in units[1:]:
		if size < next_factor:
			return size / factor, unit  # Convert to the smallest unit large enough to contain size
		factor, unit = next_factor, next_unit
	return size / factor, unit  # Overflow, convert to the current largest unit


size = 98938880
new_size, unit = convert_size(size, base_10=False)
print(f"Convert {size} Bytes -> {new_size:.2f} {unit}")
